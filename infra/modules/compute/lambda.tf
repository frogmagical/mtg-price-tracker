data "archive_file" "scheduler_zip" {
  type        = "zip"
  source_dir  = "${var.lambda_source_root}/scheduler"
  output_path = "${var.lambda_builds_dir}/scheduler.zip"
  excludes    = ["package", "__pycache__", "*.pyc"]
}

data "archive_file" "fetcher_zip" {
  type        = "zip"
  source_dir  = "${var.lambda_source_root}/fetcher"
  output_path = "${var.lambda_builds_dir}/fetcher.zip"
  excludes    = ["package", "__pycache__", "*.pyc"]
}

data "archive_file" "api_zip" {
  type        = "zip"
  source_dir  = "${var.lambda_source_root}/api"
  output_path = "${var.lambda_builds_dir}/api.zip"
  excludes    = ["package", "__pycache__", "*.pyc"]
}

resource "aws_lambda_function" "scheduler" {
  function_name    = "mtg-scheduler"
  role             = aws_iam_role.scheduler.arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  filename         = data.archive_file.scheduler_zip.output_path
  source_code_hash = data.archive_file.scheduler_zip.output_base64sha256
  memory_size      = 128
  timeout          = 300

  environment {
    variables = {
      DYNAMODB_CARDS_TABLE = var.cards_table_name
      SQS_QUEUE_URL        = var.fetch_queue_url
    }
  }

  tags = {
    Project = var.project_name
  }
}

resource "aws_lambda_function" "fetcher" {
  function_name                  = "mtg-fetcher"
  role                           = aws_iam_role.fetcher.arn
  runtime                        = "python3.12"
  handler                        = "handler.lambda_handler"
  filename                       = data.archive_file.fetcher_zip.output_path
  source_code_hash               = data.archive_file.fetcher_zip.output_base64sha256
  memory_size                    = 256
  timeout                        = 30
  reserved_concurrent_executions = 5

  environment {
    variables = {
      DYNAMODB_CARDS_TABLE  = var.cards_table_name
      DYNAMODB_PRICES_TABLE = var.prices_table_name
    }
  }

  tags = {
    Project = var.project_name
  }
}

resource "aws_lambda_event_source_mapping" "fetcher_sqs" {
  event_source_arn = var.fetch_queue_arn
  function_name    = aws_lambda_function.fetcher.arn
  batch_size       = 1
}

resource "aws_lambda_function" "api" {
  function_name    = "mtg-api"
  role             = aws_iam_role.api.arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  filename         = data.archive_file.api_zip.output_path
  source_code_hash = data.archive_file.api_zip.output_base64sha256
  memory_size      = 256
  timeout          = 10

  environment {
    variables = {
      DYNAMODB_CARDS_TABLE  = var.cards_table_name
      DYNAMODB_PRICES_TABLE = var.prices_table_name
      FETCHER_FUNCTION_NAME = aws_lambda_function.fetcher.function_name
      ADMIN_API_KEY         = var.admin_api_key
    }
  }

  tags = {
    Project = var.project_name
  }
}
