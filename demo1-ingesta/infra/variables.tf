variable "perfil" {
  description = "Perfil de AWS CLI con el que se despliega"
  type        = string
  default     = "curso"
}

variable "stream_name" {
  description = "Nombre del stream de Firehose"
  type        = string
  default     = "hp-retail-ventas"
}

variable "email_alertas" {
  description = "Email para la alarma de DataFreshness (SNS). Vacío = alarma sin notificación"
  type        = string
  default     = ""
}
