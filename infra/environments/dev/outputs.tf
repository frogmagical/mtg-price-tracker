output "api_endpoint" {
  value = module.compute.api_endpoint
}

output "cloudfront_domain" {
  value = module.frontend_hosting.cloudfront_domain
}

output "cloudfront_distribution_id" {
  value = module.frontend_hosting.cloudfront_distribution_id
}

output "frontend_bucket_name" {
  value = module.frontend_hosting.frontend_bucket_name
}

output "sqs_queue_url" {
  value = module.storage.fetch_queue_url
}
