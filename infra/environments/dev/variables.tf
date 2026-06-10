variable "aws_region" {
  default = "ap-northeast-1"
}

variable "aws_profile" {
  default = "myenv"
}

variable "env" {
  default = "prod"
}

variable "project_name" {
  default = "mtg-price-tracker"
}

variable "admin_api_key" {
  type      = string
  sensitive = true
  description = "Admin API key for write endpoints"
}
