variable "perfil" {
  description = "Perfil de AWS CLI del profesor"
  type        = string
  default     = "curso"
}

variable "principal_profesor" {
  description = "ARN del usuario o rol que asume los roles de la demo con switch role. Vacío = quien aplica"
  type        = string
  default     = ""
}
