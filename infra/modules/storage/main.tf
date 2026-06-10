resource "aws_dynamodb_table" "cards" {
  name         = "mtg-cards"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "card_name_en"

  attribute {
    name = "card_name_en"
    type = "S"
  }

  attribute {
    name = "cache_mode"
    type = "S"
  }

  attribute {
    name = "last_fetched_at"
    type = "S"
  }

  global_secondary_index {
    name            = "cache_mode-index"
    hash_key        = "cache_mode"
    range_key       = "last_fetched_at"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "TTL"
    enabled        = false
  }

  tags = {
    Project = var.project_name
  }
}

resource "aws_dynamodb_table" "prices" {
  name         = "mtg-prices"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "card_name_en"
  range_key    = "price_id"

  attribute {
    name = "card_name_en"
    type = "S"
  }

  attribute {
    name = "price_id"
    type = "S"
  }

  ttl {
    attribute_name = "TTL"
    enabled        = true
  }

  tags = {
    Project = var.project_name
  }
}

resource "aws_sqs_queue" "fetch_dlq" {
  name                        = "mtg-fetch-dlq.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  message_retention_seconds   = 1209600 # 14 days (max)

  tags = {
    Project = var.project_name
  }
}

resource "aws_sqs_queue" "fetch_queue" {
  name                        = "mtg-fetch-queue.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  visibility_timeout_seconds  = 300

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.fetch_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Project = var.project_name
  }
}
