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
