#!/usr/bin/env python3
import aws_cdk as cdk

from stack import TriageStack

app = cdk.App()
TriageStack(app, "SupportTriageCopilot", env=cdk.Environment(
    account=app.node.try_get_context("account"), region=app.node.try_get_context("region") or "eu-west-1"))
app.synth()
