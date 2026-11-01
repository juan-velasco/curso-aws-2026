{
  "family": "api-ventas",
  "requiresCompatibilities": ["FARGATE"],
  "networkMode": "awsvpc",
  "cpu": "256",
  "memory": "512",
  "runtimePlatform": { "cpuArchitecture": "ARM64", "operatingSystemFamily": "LINUX" },
  "executionRoleArn": "${execution_role_arn}",
  "taskRoleArn": "${task_role_arn}",
  "containerDefinitions": [{
    "name": "api",
    "image": "${account_id}.dkr.ecr.${region}.amazonaws.com/api-ventas:1.0.0",
    "portMappings": [{ "containerPort": 8000 }],
    "environment": [
      { "name": "FIREHOSE_STREAM", "value": "${stream_name}" },
      { "name": "AWS_REGION", "value": "${region}" }
    ],
    "logConfiguration": { "logDriver": "awslogs", "options": {
      "awslogs-group": "${log_group}", "awslogs-region": "${region}",
      "awslogs-stream-prefix": "api" } }
  }]
}
