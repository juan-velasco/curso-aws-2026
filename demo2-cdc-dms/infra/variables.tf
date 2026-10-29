variable "perfil" {
  description = "Perfil de AWS CLI con el que se despliega"
  type        = string
  default     = "curso"
}

variable "mi_ip" {
  description = "IP pública del alumno (sin /32) para conectarse a RDS. Vacío = detección automática"
  type        = string
  default     = ""
}

variable "crear_roles_dms" {
  description = "Crear dms-vpc-role y dms-cloudwatch-logs-role. false si ya existen en la cuenta"
  type        = bool
  default     = true
}

variable "version_postgres" {
  description = "Versión mayor de PostgreSQL. DMS 3.5.4+ admite 17.x como origen"
  type        = string
  default     = "17"
}

variable "clase_dms" {
  description = "Clase de la instancia de replicación. dms.t3.micro ya no se ofrece: la más pequeña es dms.t3.small"
  type        = string
  default     = "dms.t3.small"
}

variable "version_dms" {
  description = "Versión del motor de la instancia de replicación"
  type        = string
  default     = "3.6.1"
}

variable "cidr_vpc" {
  type    = string
  default = "10.20.0.0/16"
}
