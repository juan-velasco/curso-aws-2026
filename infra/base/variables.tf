variable "region" {
  description = "Región de AWS del curso"
  type        = string
  default     = "eu-west-1"
}

variable "perfil" {
  description = "Perfil de AWS CLI con el que se despliega"
  type        = string
  default     = "curso"
}

variable "sufijo_bucket" {
  description = "Sufijo del bucket del lago (los nombres de bucket son únicos en todo AWS). Vacío = ID de la cuenta"
  type        = string
  default     = ""
}

variable "email_alertas" {
  description = "Email que recibe los avisos de AWS Budgets (80 % y 100 % del presupuesto)"
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.email_alertas))
    error_message = "email_alertas debe ser una dirección de email válida."
  }
}

variable "presupuesto_usd" {
  description = "Presupuesto mensual en USD"
  type        = number
  default     = 10
}
