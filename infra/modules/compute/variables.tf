variable "project_name" {
  type = string
}

variable "lambda_source_root" {
  type = string
}

variable "lambda_builds_dir" {
  type = string
}

variable "cards_table_name" {
  type = string
}

variable "cards_table_arn" {
  type = string
}

variable "cards_cache_mode_index" {
  type = string
}

variable "prices_table_name" {
  type = string
}

variable "prices_table_arn" {
  type = string
}

variable "fetch_queue_url" {
  type = string
}

variable "fetch_queue_arn" {
  type = string
}

variable "admin_api_key" {
  type      = string
  sensitive = true
  description = "Admin API key for write endpoints (POST /cards, DELETE /cards)"
}
