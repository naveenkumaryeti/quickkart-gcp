variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "asia-south1"
}
variable "zone" {
  type    = string
  default = "asia-south1-a"
}
variable "name_prefix" {
  type    = string
  default = "quickkart"
}
variable "bucket_name" {
  type        = string
  default     = ""
  description = "Globally unique. Empty = <project_id>-quickkart-storage"
}
variable "firestore_location" {
  type    = string
  default = "asia-south1"
}
variable "machine_type" {
  type    = string
  default = "e2-medium"
}
variable "vpc_cidr_frontend" {
  type    = string
  default = "10.20.1.0/24"
}
variable "vpc_cidr_backend" {
  type    = string
  default = "10.20.2.0/24"
}
variable "backend_ilb_ip" {
  type    = string
  default = "10.20.2.10"
}
variable "domain" {
  type        = string
  default     = ""
  description = "Set a real domain to add HTTPS with a Google-managed certificate. Empty = HTTP demo."
}
variable "alert_email" {
  type    = string
  default = ""
}
variable "force_destroy_bucket" {
  type        = bool
  default     = true
  description = "Classroom default. Set false for anything you want to keep."
}
variable "retention_days" {
  type        = number
  default     = 0
  description = "Bucket retention policy in days (0 = none; a retention policy blocks deletion)."
}
