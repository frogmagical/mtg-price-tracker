# Terraform

Terraform root modules are managed per environment under `environments/`.

## Dev Deploy

```bash
cd infra/environments/dev
terraform init -reconfigure
terraform plan
terraform apply
```

Reusable modules live under `modules/`.

## Important

`terraform apply` creates AWS infrastructure, but it does not complete the full
application deployment by itself.

Manual steps after `terraform apply`:

1. Build the frontend.
2. Upload `frontend/dist` to the S3 frontend bucket.
3. Create a CloudFront invalidation.
4. Insert or import card master data into DynamoDB.
5. Run API and scheduled-fetch smoke tests.

Example frontend deploy:

```bash
cd /home/tokium/Git/MyProject/mtg-price-tracker/frontend
npm install
npm run build
aws s3 sync dist/ s3://mtg-price-frontend-571869849221/ --delete --profile myenv
aws cloudfront create-invalidation --distribution-id E22MAYUA815TXG --paths '/*' --profile myenv
```

The S3 bucket name and CloudFront distribution ID are outputs from Terraform.
Use the latest output values after re-creating the environment.

## Destroy

```bash
cd infra/environments/dev
terraform destroy
```

If the frontend S3 bucket is not empty, empty it before running destroy again:

```bash
aws s3 rm s3://mtg-price-frontend-571869849221 --recursive --profile myenv
terraform destroy
```
