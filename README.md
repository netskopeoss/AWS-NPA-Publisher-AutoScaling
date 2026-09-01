# Netskope Private Access Publisher with Amazon EC2 Auto Scaling

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Overview

This solution provides automated, cost-optimized deployment of Netskope Private Access (NPA) Publishers using Amazon EC2 Auto Scaling. It eliminates manual publisher lifecycle management through event-driven automation and provides dynamic scaling based on CPU utilization.

**Key Benefits:**
- **Automated Scaling:** Publishers automatically scale up/down based on CPU demand
- **Zero-Touch Operations:** Event-driven Lambda functions handle publisher registration/deregistration with Netskope API
- **Cost Optimization:** Pay only for capacity you need (scales down during low traffic)
- **High Availability:** Multi-AZ deployment with automatic instance replacement
- **Secure by Design:** No public IPs, egress-only security groups, encrypted secrets storage

## Solution Architecture

The solution deploys:
- Amazon EC2 Auto Scaling Group with CPU-based scaling policies (default: 70% target)
- AWS Lambda functions for automated publisher lifecycle management via Netskope REST API v2
- Amazon EventBridge rules triggering Lambda on launch/terminate events
- Auto Scaling Lifecycle Hooks for graceful publisher registration/deregistration
- AWS Secrets Manager for secure API token storage
- IAM roles with least privilege permissions
- VPC Security Group with egress-only access

![Architecture Diagram](docs/media/architecture-diagram.png)

## Quick Start

### Prerequisites

- **AWS Account** with appropriate permissions
- **Amazon VPC** with 2+ subnets in different Availability Zones
- **Outbound Connectivity** to Netskope NewEdge platform (via NAT Gateway or IPsec)
- **AWS Systems Manager** enabled for EC2 management
- **Netskope API v2 Token** with infrastructure and application management permissions
- **NPA Publisher AMI ID** for your AWS region (available on AWS Marketplace)

### Deployment Steps

1. **Get Netskope Publisher AMI ID**

   Netskope does not typically publish a public, static table of AMI IDs because these IDs change frequently as the Publisher is updated (the current version is based on Ubuntu 22.04).

   Instead, you can find the current AMI ID for your specific region using one of the three methods below:

   **Method 1: Using the AWS Management Console (Recommended)**

   This is the most reliable way to find the regional AMI for your specific account.

   - Sign in to your AWS Console and switch to the Region where you want to deploy
   - Navigate to EC2 > AMI Catalog
   - Click on the AWS Marketplace AMIs tab
   - Search for "Netskope Private Access Publisher"
   - Select the product; the specific AMI ID for that region will be displayed in the launch details or once you click "Continue to Launch"

   **Method 2: Using the Netskope Tenant UI**

   If you are already logged into your Netskope environment:

   - Go to Settings > Security Cloud Platform > Publishers
   - Click the Publisher AMI button (usually located in the top right or within the "New Publisher" setup flow)
   - This link typically redirects you to the AWS Marketplace page, which automatically detects your region and shows the corresponding ID

   **Method 3: Programmatic Lookup (Terraform/CLI)**

   Use a filter to find the latest image:

   ```bash
   aws ec2 describe-images \
       --owners aws-marketplace \
       --filters "Name=name,Values=*Netskope Private Access Publisher*" \
       --region <your-region> \
       --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
       --output text
   ```

2. **Configure Parameters**
   - Netskope Tenant FQDN (e.g., `mytenant.goskope.com`)
   - VPC and Subnet IDs (minimum 2 subnets in different AZs)
   - NPA Publisher Group Name
   - Min/Max/Desired capacity (recommended: min 2, max 10)
   - API Token (new or existing Secrets Manager ARN)

3. **Deploy CloudFormation Stack**
   ```bash
   aws cloudformation create-stack \
     --stack-name netskope-npa-publisher \
     --template-body file://templates/npa-publisher-autoscaling.yaml \
     --parameters file://parameters.json \
     --capabilities CAPABILITY_NAMED_IAM
   ```

4. **Verify Deployment**
   - Check CloudFormation stack status: `CREATE_COMPLETE`
   - Verify Auto Scaling Group has launched instances
   - Check Lambda function logs in CloudWatch
   - Confirm publishers registered in Netskope tenant

> **For detailed step-by-step instructions with screenshots, see the [Detailed Deployment Guide](docs/DEPLOYMENT_GUIDE.md)**

### Naming Convention Requirement

**CRITICAL:** This solution requires specific naming conventions to function properly. Private Applications in Netskope must follow this naming pattern:

```
Auto Scaling Group Name: MyNPAPublisherGroup
Valid App Names: MyNPAPublisherGroup-App1
                 MyNPAPublisherGroup-WebServer
                 MyNPAPublisherGroup-Database
```

The Lambda function uses this prefix matching to identify which apps belong to this publisher group for automatic configuration updates.

> **For detailed naming convention requirements and modification instructions, see:** [DevOps Notes - Naming Convention Requirement](docs/DEVOPS_NOTES.md#naming-convention-requirement)

## Documentation

- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Detailed step-by-step deployment instructions with screenshots
- **[DevOps Notes](docs/DEVOPS_NOTES.md)** - Technical solution overview, architecture details, AWS services used
- **[NPA HA Strategies](docs/NPA_AWS_HA_STRATEGIES.md)** - High availability design patterns

## Project Structure

```
/
├── templates/                          # CloudFormation templates
│   └── npa-publisher-autoscaling.yaml  # Main template
├── scripts/                            # Lambda function code
│   ├── lambda_function.py              # Lifecycle management function
│   └── NPAPublisherAutoscalling.zip    # Packaged Lambda deployment
├── docs/                               # Documentation
│   ├── DEPLOYMENT_GUIDE.md             # Detailed deployment guide with screenshots
│   ├── DEVOPS_NOTES.md                 # Technical overview
│   └── media/                          # Architecture diagrams and screenshots
├── .gitignore                          # Git ignore rules
├── LICENSE                             # Apache 2.0 license
└── README.md                           # This file
```

## Features

### Dynamic Scaling
- CPU-based target tracking scaling policy
- Configurable thresholds (default: 70% CPU)
- Cooldown period: 5 minutes between scaling events
- Graceful scale-in with lifecycle hooks

### Automated Publisher Management
- Automatic registration with Netskope on instance launch
- Automatic deregistration on instance termination
- Automatic private application configuration updates
- SSM Run Command for secure publisher provisioning

### Security & Compliance
- No public IP addresses assigned to publishers
- Security group with zero ingress rules (egress only)
- API tokens stored in AWS Secrets Manager
- IAM roles following least privilege principle
- Access via AWS Systems Manager Session Manager
- VPC-based network isolation

### High Availability
- Multi-AZ deployment support
- Automatic instance health checks
- Failed instance replacement
- Configurable minimum capacity (recommended: 2)

### Cost Optimization
- Scale down during low traffic periods
- Configurable capacity limits
- Resource tagging for cost allocation
- Right-sized instance types (t3.large default)

## Cost Estimation

| Deployment Size | Instances | Estimated Monthly Cost* |
|-----------------|-----------|------------------------|
| Small           | 2-4       | $200-400               |
| Medium          | 4-8       | $400-800               |
| Large           | 8-16      | $800-1,600             |

*Costs include EC2 (t3.large), NAT Gateway, Lambda, Secrets Manager. Actual costs vary by region, data transfer, and usage patterns.

## Multi-Region Deployment

Deploy the same Auto Scaling Group name in multiple AWS regions to provide:
- Geographic redundancy
- Disaster recovery
- Lower latency for global users

Example:
```
Publisher Group: MyNPAPublisher
├─ us-east-1: 2-5 instances
├─ us-west-2: 2-5 instances
└─ eu-west-1: 2-5 instances

All serve: MyNPAPublisher-App1, MyNPAPublisher-App2
```

## Monitoring

### CloudWatch Metrics
- Auto Scaling Group CPU utilization
- Instance count (min/max/desired/current)
- Scaling activity history
- Lambda function invocations and errors

### CloudWatch Logs
- Lambda function execution logs
- Publisher registration/deregistration events
- SSM Run Command output
- API call responses and errors

### Recommended Alarms
- High CPU utilization (>80% for 10 minutes)
- Lambda function errors
- Auto Scaling Group capacity at maximum
- Failed publisher registrations

## Troubleshooting

### Publishers Not Registering
1. Check Lambda function logs in CloudWatch
2. Verify Netskope API token has correct permissions
3. Check VPC connectivity to Netskope NewEdge
4. Verify SSM agent running on EC2 instances

### Scaling Not Working
1. Check Auto Scaling Group scaling policies
2. Verify CloudWatch metrics are being received
3. Review scaling activity history
4. Check lifecycle hook timeouts

### Private Apps Not Updated
1. Verify app names follow naming convention
2. Check Lambda function has app management permissions
3. Review Lambda logs for API call errors

See [DevOps Notes](docs/DEVOPS_NOTES.md) for detailed resolution steps.

## Support

For issues, questions, or contributions:
- **GitHub Issues:** [Report a bug or request a feature](https://github.com/netskopeoss/AWS-NPA-Publisher-AutoScaling/issues)
- **Netskope Docs:** [Private Access Documentation](https://docs.netskope.com/en/netskope-private-access.html)
- **Netskope API:** [REST API v2 Documentation](https://docs.netskope.com/en/rest-api-v2-overview-312207.html)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

Please ensure:
- CloudFormation templates pass cfn-lint validation
- Code follows security best practices
- Documentation is updated
- Changes are tested in a non-production environment

## Acknowledgments

- Built for integration with [Netskope Private Access](https://www.netskope.com/products/private-access)

---

**Maintained by:** Netskope OSS Community
**Version:** 1.0
**Last Updated:** 2025-12-16
