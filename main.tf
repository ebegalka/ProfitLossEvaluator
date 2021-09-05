//
//PROVIDER
//

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 3.0"
    }
  }
}

# Configure the AWS Provider
provider "aws" {
  region = "us-east-1"
}

data "aws_caller_identity" "current" {}

//
//ROLE
//

resource "aws_iam_role" "tf_ple_lambda_role" {
  name               = "tf_ple_lambda_role"
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}

resource "aws_iam_policy" "tf_ple_lambda_policy" {
  name = "tf_ple_lambda_policy"
  #role = aws_iam_role.tf_ple_lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "sqs:*"
        ]
        Effect   = "Allow"
        Resource = "*"
      },
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Action = [
          "kms:Decrypt"
        ]
        Effect   = "Allow"
        Resource = "${aws_kms_key.tf_ple_kms_key.arn}"
      },
      {
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:secretsmanager:*:${data.aws_caller_identity.current.account_id}:secret:finnhub_api_key*"
      },
      {
        Action = [
          "s3:PutObject*"
        ]
        Effect = "Allow"
        Resource = [
          "${aws_s3_bucket.tf_ple_member_balance_bucket.arn}",
          "${aws_s3_bucket.tf_ple_member_balance_bucket.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_policy_attachment" "tf_ple_policy_attachment" {
  name       = "tf_ple_policy_attachment"
  roles      = [aws_iam_role.tf_ple_lambda_role.name]
  policy_arn = aws_iam_policy.tf_ple_lambda_policy.arn
}

//SECRET

resource "aws_kms_key" "tf_ple_kms_key" {
  policy = <<EOF
{
    "Version": "2008-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": [
                    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/EthanAdminUser",
                    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root",
                    "${aws_iam_role.tf_ple_lambda_role.arn}"
                ]
            },
            "Action": "kms:*",
            "Resource": "*"
        }
    ]
}
EOF
}

resource "aws_kms_alias" "tf_ple_kms_key_alias" {
  name          = "alias/tf_ple_kms_key"
  target_key_id = aws_kms_key.tf_ple_kms_key.key_id
}

//SQS

resource "aws_sqs_queue" "tf_ple_sqs_queue" {
  name                      = "tf_ple_sqs_queue"
  max_message_size          = 2048
  message_retention_seconds = 86400
}

resource "aws_lambda_event_source_mapping" "tf_ple_event_source_mapping" {
  event_source_arn = aws_sqs_queue.tf_ple_sqs_queue.arn
  function_name    = aws_lambda_function.tf_ple_function.arn
  batch_size       = 1
}


//
//LAMBDA FUNCTION
//

resource "aws_lambda_layer_version" "tf_ple_lambda_layer_pandas" {
  filename            = "layers/pandas_layer.zip"
  layer_name          = "pandas"
  compatible_runtimes = ["python3.8"]
}

resource "aws_lambda_layer_version" "tf_ple_lambda_layer_finnhub" {
  filename            = "layers/finnhub_layer.zip"
  layer_name          = "finnhub"
  compatible_runtimes = ["python3.8"]
}

variable "lambda_function_name" {
  default = "tf_ple_function"
}

data "archive_file" "lambda_my_function" {
  type             = "zip"
  source_file      = "lambda_function.py"
  output_file_mode = "0666"
  output_path      = "ple_function.zip"
}

resource "aws_lambda_function" "tf_ple_function" {
  function_name    = var.lambda_function_name
  filename         = "ple_function.zip"
  source_code_hash = data.archive_file.lambda_my_function.output_base64sha256
  role             = aws_iam_role.tf_ple_lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  timeout          = 30
  layers = [
    aws_lambda_layer_version.tf_ple_lambda_layer_finnhub.arn,
    aws_lambda_layer_version.tf_ple_lambda_layer_pandas.arn
  ]

  runtime = "python3.8"

  depends_on = [
    aws_cloudwatch_log_group.tf_ple_cloudwatch_lambda_log_group,
  ]
}

//
//LOGGING
//

resource "aws_cloudwatch_log_group" "tf_ple_cloudwatch_lambda_log_group" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = 14
}

//
// S3 OUPUT
//

resource "aws_s3_bucket" "tf_ple_member_balance_bucket" {
  bucket = "tf-ple-user-balance-bucket"
  acl    = "private"
  versioning {
    enabled = true
  }
}

