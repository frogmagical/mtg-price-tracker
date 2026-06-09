output "api_endpoint" {
  value = aws_apigatewayv2_api.main.api_endpoint
}

output "fetcher_function_arn" {
  value = aws_lambda_function.fetcher.arn
}
