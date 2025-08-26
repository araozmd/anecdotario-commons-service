#!/bin/bash

# Deploy Commons Service CI/CD Pipeline
# Usage: ./deploy-pipeline.sh <github-token>

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <github-token>"
    echo "Example: $0 ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    exit 1
fi

GITHUB_TOKEN=$1
STACK_NAME="anecdotario-commons-pipeline"

echo "🚀 Deploying Commons Service CI/CD Pipeline..."

# Deploy the pipeline CloudFormation stack
aws cloudformation deploy \
  --template-file pipeline/pipeline-template.yaml \
  --stack-name $STACK_NAME \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    GitHubToken=$GITHUB_TOKEN \
    GitHubOwner=araozmd \
    GitHubRepo=anecdotario-commons-service \
    GitHubBranch=main \
  --tags \
    Service=commons-service \
    Environment=pipeline \
    Project=anecdotario \
    ManagedBy=cloudformation

if [ $? -eq 0 ]; then
    echo "✅ Pipeline deployed successfully!"
    
    # Get pipeline URL
    PIPELINE_URL=$(aws cloudformation describe-stacks \
      --stack-name $STACK_NAME \
      --query 'Stacks[0].Outputs[?OutputKey==`PipelineUrl`].OutputValue' \
      --output text)
    
    echo "📊 Pipeline URL: $PIPELINE_URL"
    
    # Get approval topic ARN
    APPROVAL_TOPIC=$(aws cloudformation describe-stacks \
      --stack-name $STACK_NAME \
      --query 'Stacks[0].Outputs[?OutputKey==`ApprovalTopicArn`].OutputValue' \
      --output text)
    
    echo "📧 Approval Topic ARN: $APPROVAL_TOPIC"
    echo ""
    echo "🔔 To receive approval notifications, subscribe to the SNS topic:"
    echo "aws sns subscribe --topic-arn $APPROVAL_TOPIC --protocol email --notification-endpoint your-email@example.com"
    
else
    echo "❌ Pipeline deployment failed!"
    exit 1
fi