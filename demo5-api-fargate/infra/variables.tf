variable "perfil" {
  description = "Perfil de AWS CLI"
  type        = string
  default     = "curso"
}

variable "cidr_vpc" {
  description = "Rango de la VPC de la API"
  type        = string
  default     = "10.40.0.0/16"
}

variable "mi_ip" {
  description = "IP desde la que se llama a la API. Vacío = detectarla con checkip.amazonaws.com"
  type        = string
  default     = ""
}
