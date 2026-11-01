variable "perfil" {
  description = "Perfil de AWS CLI"
  type        = string
  default     = "curso"
}

variable "cidr_vpc" {
  description = "Rango de la VPC de Studio"
  type        = string
  default     = "10.50.0.0/16"
}

variable "instancia_jupyterlab" {
  description = "Tipo de instancia por defecto de los spaces de JupyterLab"
  type        = string
  default     = "ml.t3.medium"
}

variable "minutos_inactividad" {
  description = "JupyterLab se apaga solo tras estos minutos sin actividad"
  type        = number
  default     = 60
}

variable "quicksight_activo" {
  description = "Crea el dataset prevision_vs_real. Requiere Amazon Quick y haber lanzado preparar_datos.py"
  type        = bool
  default     = false
}

variable "quicksight_usuario_arn" {
  description = "ARN del usuario Author de QuickSight (aws quicksight list-users)"
  type        = string
  default     = ""
}
