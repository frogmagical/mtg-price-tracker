terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

data "aws_caller_identity" "current" {}

module "storage" {
  source = "../../modules/storage"

  project_name = var.project_name
}

module "compute" {
  source = "../../modules/compute"

  project_name           = var.project_name
  lambda_source_root     = "${path.root}/../../../backend/lambda"
  lambda_builds_dir      = "${path.root}/../../builds"
  cards_table_name       = module.storage.cards_table_name
  cards_table_arn        = module.storage.cards_table_arn
  cards_cache_mode_index = module.storage.cards_cache_mode_index_name
  prices_table_name      = module.storage.prices_table_name
  prices_table_arn       = module.storage.prices_table_arn
  fetch_queue_url        = module.storage.fetch_queue_url
  fetch_queue_arn        = module.storage.fetch_queue_arn
  admin_api_key          = var.admin_api_key
}

module "frontend_hosting" {
  source = "../../modules/frontend_hosting"

  project_name = var.project_name
  account_id   = data.aws_caller_identity.current.account_id
}
