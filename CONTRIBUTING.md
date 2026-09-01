# Contributing Guidelines

Thank you for your interest in contributing to the AWS NPA Publisher AutoScaling project! This document provides guidelines and best practices for contributing.

## Code of Conduct

This project adheres to the Amazon Open Source Code of Conduct. By participating, you are expected to uphold this code.

## How to Contribute

### Reporting Issues

- Check existing issues before creating a new one
- Provide detailed information including CloudFormation template version, AWS region, and error messages
- Include relevant CloudWatch Logs from Lambda functions
- Describe expected vs actual behavior

### Submitting Changes

1. **Fork the repository** and create your branch from `main`
2. **Create a feature branch** with a descriptive name:
   ```bash
   git checkout -b feature/add-new-capability
   git checkout -b fix/publisher-lifecycle-bug
   ```
3. **Make your changes** following the guidelines below
4. **Test thoroughly** - ensure all validation checks pass
5. **Commit your changes** with clear, descriptive messages
6. **Push to your fork** and submit a pull request

## Development Setup

### Prerequisites

- Python 3.12 or later
- AWS CLI configured with appropriate credentials
- Git

### Install Development Tools

```bash
validation tools
pip install cfn-lint detect-secrets bandit flake8 black
```

## Validation Requirements

All contributions must pass the automated validation checks in our CI/CD pipeline.

### 1. CloudFormation Validation

Validate templates using cfn-lint:
```bash
cfn-lint --version
cfn-lint templates/*.yaml --format parseable --ignore-checks W
```

**Requirements:**
- Templates must be valid CloudFormation syntax
- Use partition-agnostic ARNs: `${AWS::Partition}` instead of hardcoded `aws`
- Follow AWS CloudFormation best practices
- Include meaningful descriptions for all resources
- Use appropriate DeletionPolicy where needed

### 2. Secret Scanning

Prevent secrets from being committed:
```bash
detect-secrets --version
detect-secrets scan --all-files --baseline .secrets.baseline
```

**Requirements:**
- No AWS credentials, API tokens, or private keys in code
- Use AWS Secrets Manager or AWS Systems Manager Parameter Store for secrets
- Update `.secrets.baseline` if adding legitimate test data that triggers false positives

### 3. Python Code Quality

Python code must pass security and quality checks:

#### Bandit (Security Scanner)
```bash
bandit -ll --skip B101 -r scripts/
```

**Requirements:**
- No high or medium severity security issues
- Follow OWASP secure coding practices
- Validate all external inputs


#### Flake8 (Linter)
```bash
flake8 --max-line-length=120 --extend-ignore=E203,W503 scripts/
```

**Requirements:**
- Maximum line length: 120 characters
- Follow PEP 8 style guide
- No unused imports or variables

#### Black (Code Formatter)
```bash
black --check scripts/
# Or auto-format:
black scripts/
```

### 4. File Quality

- **No trailing whitespace**
- **No merge conflict markers**
- **No files larger than 1MB** (use Git LFS for large files)

Run checks:
```bash
# Check trailing whitespace
git grep -I --line-number '[[:blank:]]$' -- ':!*.patch' ':!*.diff'

# Remove trailing whitespace
find scripts/ templates/ -type f -exec sed -i '' 's/[[:blank:]]*$//' {} \;
```

## Code Standards

### CloudFormation Templates

- **Naming Convention**: Use PascalCase for resource logical IDs
- **Parameters**: Provide sensible defaults where appropriate
- **Outputs**: Export important resource ARNs and IDs
- **Comments**: Add description metadata for all parameters and resources
- **Tags**: Include appropriate tags for cost allocation

Example:
```yaml
NPAPublisherSecurityGroup:
  Type: AWS::EC2::SecurityGroup
  Metadata:
    cfn-lint:
      config:
        ignore_checks:
          - E3030  # With justification
  Properties:
    GroupDescription: Security group for NPA Publisher instances
    VpcId: !Ref VPCId
    Tags:
      - Key: Name
        Value: !Sub '${AWS::StackName}-publisher-sg'
```

### Python Code (Lambda Functions)

- **Error Handling**: Use try/except blocks and log errors properly
- **Logging**: Use structured logging with appropriate log levels
- **Retries**: Implement retry logic with exponential backoff for API calls
- **Timeouts**: Set appropriate timeout values
- **Type Hints**: Use type hints for function parameters and returns

Example:
```python
import boto3
from botocore.exceptions import ClientError
from utils.logger import Logger
import time

logger = Logger(loglevel='info')

def call_netskope_api(method: str, api_url: str, token: str, payload: dict) -> dict:
    """Call Netskope API with retry logic.

    Args:
        method: HTTP method (get, post, patch, delete)
        api_url: API endpoint path
        token: API authentication token
        payload: Request payload

    Returns:
        dict: API response
    """
    try:
        # Implementation
        pass
    except Exception as e:
        logger.error(f'API call failed: {str(e)}')
        raise
```

### Documentation

- **README**: Keep README current with major changes
- **Inline Comments**: Explain complex logic and business rules
- **Docstrings**: Document all functions with parameters and return values
- **Architecture Diagrams**: Update diagrams when architecture changes

## Commit Message Guidelines

Follow conventional commit format:

```
<type>: <short summary>

<detailed description>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat: Add support for cross-region publisher groups

Implement functionality to deploy NPA publishers across multiple
AWS regions while maintaining centralized configuration.

Closes #123
```

```
fix: Resolve publisher deprovisioning race condition

Add lifecycle hook timeout handling to prevent orphaned publishers
when EC2 instances terminate rapidly.

Fixes #456
```

## Pull Request Guidelines

### PR Title

Use the same format as commit messages:
```
feat: Add CloudWatch dashboard for publisher metrics
fix: Correct IAM policy for cross-account access
```

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Breaking change

## Testing
Describe testing performed:
- [ ] Validated CloudFormation template with cfn-lint
- [ ] Tested in AWS account (region: us-east-1)
- [ ] Verified publisher lifecycle (launch/terminate)
- [ ] Checked Lambda function logs

## Checklist
- [ ] Code follows project style guidelines
- [ ] All validation checks pass
- [ ] Documentation updated
- [ ] Commit messages follow guidelines
- [ ] No secrets in code
- [ ] Backward compatible (or breaking change documented)

## Related Issues
Closes #123
```

### Review Process

- PRs require at least one approval
- All CI/CD checks must pass
- Address reviewer feedback promptly
- Keep PRs focused and reasonably sized

## Security Best Practices

### Secrets Management

- **NEVER** commit credentials, API tokens, or private keys
- Use AWS Secrets Manager for sensitive data
- Reference secrets using ARNs in CloudFormation
- Rotate secrets regularly

### IAM Permissions

- Follow principle of least privilege
- Use IAM roles instead of access keys
- Document required permissions in README
- Use managed policies where appropriate

### Network Security

- Use security groups with minimal required ports
- Implement VPC endpoints where possible
- Enable VPC Flow Logs for troubleshooting
- Use private subnets for EC2 instances

## Testing

### Local Testing

Before submitting PR:

```bash
# Run all validation checks
cfn-lint templates/*.yaml --format parseable --ignore-checks W
detect-secrets scan --all-files --baseline .secrets.baseline
bandit -ll --skip B101 -r scripts/
flake8 --max-line-length=120 --extend-ignore=E203,W503 scripts/
black --check scripts/

# Check for file quality issues
git grep -I --line-number '[[:blank:]]$'  # No trailing whitespace
git grep -I --line-number '^<<<<<<< '    # No merge conflicts
```

### CloudFormation Testing

Test CloudFormation templates:

```bash
# Validate template syntax
aws cloudformation validate-template \
  --template-body file://templates/npa-publisher-autoscaling.yaml

# Create change set (dry run)
aws cloudformation create-change-set \
  --stack-name test-npa-publisher \
  --template-body file://templates/npa-publisher-autoscaling.yaml \
  --parameters file://test-parameters.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --change-set-name test-changeset

# Review change set
aws cloudformation describe-change-set \
  --stack-name test-npa-publisher \
  --change-set-name test-changeset
```

### Lambda Function Testing

- Test Lambda functions with sample events
- Verify IAM permissions are sufficient
- Check CloudWatch Logs for errors
- Test with actual Auto Scaling group events

## Versioning

- We use Semantic Versioning (SemVer)
- Tag releases: `v1.0.0`, `v1.1.0`, `v2.0.0`
- Update CHANGELOG.md for each release

## Questions?

- Open an issue for questions about contributing
- Tag maintainers for urgent clarifications
- Check existing issues and PRs for similar questions

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.

---

Thank you for contributing to make this project better!
