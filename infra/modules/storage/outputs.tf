output "cards_table_name" {
  value = aws_dynamodb_table.cards.name
}

output "cards_table_arn" {
  value = aws_dynamodb_table.cards.arn
}

output "cards_cache_mode_index_name" {
  value = "cache_mode-index"
}

output "prices_table_name" {
  value = aws_dynamodb_table.prices.name
}

output "prices_table_arn" {
  value = aws_dynamodb_table.prices.arn
}

output "fetch_queue_url" {
  value = aws_sqs_queue.fetch_queue.url
}

output "fetch_queue_arn" {
  value = aws_sqs_queue.fetch_queue.arn
}
