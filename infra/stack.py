import json
from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_opensearchserverless as aoss
from aws_cdk import aws_s3 as s3
from constructs import Construct

NAMESPACE = "SupportTriage"
COLLECTION = "support-triage-kb"  # AOSS names: 3-32 chars, lowercase
INDEX = "kb-chunks"
GSI = "category-created-index"
DECISION_GSI = "decision-index"
AUTO_CATEGORIES = ["password_reset", "shipping_status", "product_how_to", "account_settings", "general_inquiry"]


class TriageStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # ---------------- data plane ----------------
        kb_bucket = s3.Bucket(
            self, "KbBucket", versioned=True, enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED, removal_policy=RemovalPolicy.RETAIN,
        )
        tickets = ddb.Table(
            self, "Tickets", partition_key=ddb.Attribute(name="ticket_id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST, point_in_time_recovery=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        feedback = ddb.Table(
            self, "Feedback", partition_key=ddb.Attribute(name="ticket_id", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="feedback_id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST, point_in_time_recovery=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        feedback.add_global_secondary_index(
            index_name=GSI,
            partition_key=ddb.Attribute(name="category", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="created_at", type=ddb.AttributeType.STRING),
            projection_type=ddb.ProjectionType.ALL,
        )
        # Powers GET /v1/tickets/AI_drafted_tickets and /Escalated_tickets (queried on the *Tickets* table).
        tickets.add_global_secondary_index(
            index_name=DECISION_GSI,
            partition_key=ddb.Attribute(name="decision", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="created_at", type=ddb.AttributeType.STRING),
            projection_type=ddb.ProjectionType.ALL,
        )

        # ---------------- OpenSearch Serverless (vector search) ----------------
        enc = aoss.CfnSecurityPolicy(self, "KbEnc", name="triage-kb-enc", type="encryption", policy=json.dumps(
            {"Rules": [{"ResourceType": "collection", "Resource": [f"collection/{COLLECTION}"]}], "AWSOwnedKey": True}))
        net = aoss.CfnSecurityPolicy(self, "KbNet", name="triage-kb-net", type="network", policy=json.dumps(
            [{"Rules": [{"ResourceType": "collection", "Resource": [f"collection/{COLLECTION}"]}],
              # Public endpoint, but every call must be SigV4-signed AND allowed by the data policy below.
              # For stricter isolation, swap for a VPC endpoint (AllowFromPublic False + SourceVPCEs).
              "AllowFromPublic": True}]))
        collection = aoss.CfnCollection(self, "KbCollection", name=COLLECTION, type="VECTORSEARCH")
        collection.add_dependency(enc)
        collection.add_dependency(net)

        ## ---------------- IAM ----------------
        task_role = iam.Role(self, "TaskRole", assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"))
        kb_bucket.grant_read(task_role)
        tickets.grant_read_write_data(task_role)
        feedback.grant_read_write_data(task_role)
        task_role.add_to_policy(iam.PolicyStatement(actions=["aoss:APIAccessAll"], resources=[collection.attr_arn]))
        # Scope to specific model ARNs / inference profiles once you've chosen models.
        task_role.add_to_policy(iam.PolicyStatement(actions=["bedrock:InvokeModel"], resources=["*"]))

       
        principals = [task_role.role_arn]
        ingest_principal = self.node.try_get_context("ingest_principal_arn")
        if ingest_principal:
            principals.append(ingest_principal)
        access = aoss.CfnAccessPolicy(self, "KbAccess", name="triage-kb-access", type="data", policy=json.dumps([{
            "Principal": principals,
            "Rules": [
                {"ResourceType": "collection", "Resource": [f"collection/{COLLECTION}"],
                 "Permission": ["aoss:DescribeCollectionItems"]},
                {"ResourceType": "index", "Resource": [f"index/{COLLECTION}/*"],
                 "Permission": ["aoss:CreateIndex", "aoss:DescribeIndex", "aoss:UpdateIndex",
                                "aoss:ReadDocument", "aoss:WriteDocument"]},
            ],
        }]))
        collection.add_dependency(access)

        # ---------------- compute: ECS Fargate behind an ALB ----------------
        vpc = ec2.Vpc(self, "Vpc", max_azs=2, nat_gateways=1)
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc, container_insights=True)
        repo_root = Path(__file__).resolve().parent.parent

        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "Service", cluster=cluster, cpu=512, memory_limit_mib=1024, desired_count=2,
            public_load_balancer=True, min_healthy_percent=100, max_healthy_percent=200,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.X86_64, operating_system_family=ecs.OperatingSystemFamily.LINUX),
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset(str(repo_root), platform=ecr_assets.Platform.LINUX_AMD64),
                container_port=8000, task_role=task_role,
                log_driver=ecs.LogDrivers.aws_logs(stream_prefix="triage", log_retention=logs.RetentionDays.ONE_MONTH),
                environment={
                    "TRIAGE_BACKEND": "aws",
                    "TRIAGE_AWS_REGION": self.region,
                    "TRIAGE_OPENSEARCH_ENDPOINT": collection.attr_collection_endpoint,
                    "TRIAGE_OPENSEARCH_INDEX": INDEX,
                    "TRIAGE_KB_BUCKET": kb_bucket.bucket_name,
                    "TRIAGE_TICKETS_TABLE": tickets.table_name,
                    "TRIAGE_TICKETS_DECISION_INDEX": DECISION_GSI,
                    "TRIAGE_FEEDBACK_TABLE": feedback.table_name,
                    "TRIAGE_FEEDBACK_CATEGORY_INDEX": GSI,
                    "TRIAGE_METRICS_NAMESPACE": NAMESPACE,
                    # Tune routing here (a redeploy rolls the new threshold out safely):
                    "TRIAGE_ACCEPTANCE_THRESHOLD": "0.75",
                    "TRIAGE_MIN_GROUNDING_SCORE": "0.35",
                },
            ),
        )
        service.target_group.configure_health_check(path="/healthz", healthy_http_codes="200",
                                                    interval=Duration.seconds(15))
        service.target_group.set_attribute("deregistration_delay.timeout_seconds", "30")
        scaling = service.service.auto_scale_task_count(min_capacity=2, max_capacity=6)
        scaling.scale_on_cpu_utilization("Cpu", target_utilization_percent=60)

        # ---------------- observability: drift dashboard + alarm ----------------
        def m(name: str, category: str | None = None, stat: str = "Sum", period: Duration = Duration.days(1)) -> cw.Metric:
            return cw.Metric(namespace=NAMESPACE, metric_name=name, statistic=stat, period=period,
                             dimensions_map={"Category": category} if category else None)

        def acceptance(category: str | None = None, period: Duration = Duration.days(1)) -> cw.MathExpression:
            return cw.MathExpression(
                expression="a / (a + e + r)", label=category or "all categories", period=period,
                using_metrics={"a": m("FeedbackAccept", category, period=period),
                               "e": m("FeedbackEdit", category, period=period),
                               "r": m("FeedbackReject", category, period=period)})

        dash = cw.Dashboard(self, "DriftDashboard", dashboard_name="support-triage-drift")
        dash.add_widgets(
            cw.GraphWidget(title="Acceptance rate (daily, all categories)", left=[acceptance()], left_y_axis=cw.YAxisProps(min=0, max=1), width=12),
            cw.GraphWidget(title="Acceptance rate by category (daily)", left=[acceptance(c) for c in AUTO_CATEGORIES], left_y_axis=cw.YAxisProps(min=0, max=1), width=12),
        )
        dash.add_widgets(
            cw.GraphWidget(title="Agent feedback volume", stacked=True, width=12, period=Duration.days(1),
                           left=[m("FeedbackAccept"), m("FeedbackEdit"), m("FeedbackReject")]),
            cw.GraphWidget(title="Routing decisions", stacked=True, width=12, period=Duration.hours(1),
                           left=[m("DecisionDraftReady", period=Duration.hours(1)),
                                 m("DecisionHumanTriage", period=Duration.hours(1)),
                                 m("DecisionEscalate", period=Duration.hours(1))]),
        )
        dash.add_widgets(
            cw.GraphWidget(title="Mean classifier confidence (drift signal)", width=12, period=Duration.days(1),
                           left=[m("Confidence", stat="Average")]),
            cw.GraphWidget(title="Mean edit ratio on edited drafts (0 = unchanged, 1 = rewritten)", width=12, period=Duration.days(1),
                           left=[m("EditRatio", stat="Average")]),
        )

        # Alarm when the daily acceptance rate sits under 60% for 3 days, ignoring low-volume days.
        a, e, r = m("FeedbackAccept"), m("FeedbackEdit"), m("FeedbackReject")
        cw.Alarm(
            self, "AcceptanceDrift", alarm_description="Draft acceptance rate below 60% for 3 consecutive days",
            metric=cw.MathExpression(expression="IF((a + e + r) >= 20, a / (a + e + r), 1)",
                                     using_metrics={"a": a, "e": e, "r": r}, period=Duration.days(1)),
            threshold=0.6, evaluation_periods=3, datapoints_to_alarm=3,
            comparison_operator=cw.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )

        CfnOutput(self, "ApiUrl", value=f"http://{service.load_balancer.load_balancer_dns_name}")
        CfnOutput(self, "KbBucketName", value=kb_bucket.bucket_name)
        CfnOutput(self, "CollectionEndpoint", value=collection.attr_collection_endpoint)
        CfnOutput(self, "TicketsTable", value=tickets.table_name)
        CfnOutput(self, "FeedbackTable", value=feedback.table_name)
