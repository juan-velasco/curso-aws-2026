variable "perfil" {
  description = "Perfil de AWS CLI"
  type        = string
  default     = "curso"
}

variable "clase_ejecucion_glue" {
  description = "STANDARD en la demo; FLEX (más barata, puede tardar en arrancar) para la programación horaria"
  type        = string
  default     = "STANDARD"
}

variable "cidr_vpc" {
  description = "Rango de la VPC de Redshift"
  type        = string
  default     = "10.30.0.0/16"
}

variable "cidr_quicksight" {
  description = "Rango de IP de QuickSight en eu-west-1, de docs.aws.amazon.com/quicksight/latest/user/regions.html"
  type        = string
  default     = "52.210.255.224/27"
}

variable "mi_ip" {
  description = "IP del profesor para conectar a Redshift. Vacío = detectarla con checkip.amazonaws.com"
  type        = string
  default     = ""
}

variable "rpu_base" {
  description = "Capacidad base de Redshift Serverless. 4 es la mínima admitida"
  type        = number
  default     = 4
}

variable "email_alertas" {
  description = "Email que recibe los avisos del pipeline (SNS). Hay que confirmar la suscripción"
  type        = string
}

variable "programacion_activa" {
  description = "Activa la ejecución horaria del pipeline. En FLEX, con clase_ejecucion_glue"
  type        = bool
  default     = false
}

variable "quicksight_activo" {
  description = "Crea la fuente de datos y el dataset. Requiere la suscripción manual a QuickSight"
  type        = bool
  default     = false
}

variable "quicksight_usuario_arn" {
  description = "ARN del usuario Author de QuickSight (aws quicksight list-users)"
  type        = string
  default     = ""
}
