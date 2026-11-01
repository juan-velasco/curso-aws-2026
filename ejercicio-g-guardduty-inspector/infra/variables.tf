variable "perfil" {
  description = "Perfil de AWS CLI"
  type        = string
  default     = "curso"
}

variable "email_alertas" {
  description = "Email que recibe los hallazgos graves (SNS). Hay que confirmar la suscripción"
  type        = string
}

# Dos interruptores decididos con estado_servicios.py. Con el servicio ya activo o gestionado por
# la organización, se dejan en false: destroy solo desactiva lo que haya activado este módulo.
variable "crear_detector_guardduty" {
  description = "Crea el detector de GuardDuty. Solo si estado_servicios.py dice que no hay ninguno"
  type        = bool
  default     = false
}

variable "activar_inspector_ecr" {
  description = "Activa Inspector para ECR. Solo si estado_servicios.py lo muestra desactivado"
  type        = bool
  default     = false
}
