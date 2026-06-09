resource "aws_scheduler_schedule" "daily" {
  name = "mtg-daily-scheduler"

  flexible_time_window {
    mode = "OFF"
  }

  # cron(0 2 * * ? *) = UTC 02:00 = JST 11:00
  schedule_expression          = "cron(0 2 * * ? *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = aws_lambda_function.scheduler.arn
    role_arn = aws_iam_role.eventbridge_scheduler.arn
  }
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scheduler.function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.daily.arn
}
