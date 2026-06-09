terraform {
  backend "s3" {
    bucket       = "mkhookah-terraform"
    key          = "mtg-price-tracker/backend/dev/terraform.tfstate"
    region       = "ap-northeast-1"
    encrypt      = true
    profile      = "myenv"
    use_lockfile = true
  }
}
