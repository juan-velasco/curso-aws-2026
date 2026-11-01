# Reutiliza la fuente de datos de la demo 4. El dataset exige que gold.v_prevision_vs_real exista.

data "terraform_remote_state" "demo4" {
  count   = var.quicksight_activo ? 1 : 0
  backend = "local"
  config  = { path = "${path.module}/../../demo4-pipeline/infra/terraform.tfstate" }
}

locals {
  id_dataset = "prevision_vs_real"

  columnas_prevision = {
    fecha              = "DATETIME"
    fecha_sk           = "INTEGER"
    pais               = "STRING"
    familia            = "STRING"
    unidades_reales    = "DECIMAL"
    unidades_previstas = "DECIMAL"
  }
}

resource "aws_quicksight_data_set" "prevision" {
  count       = var.quicksight_activo ? 1 : 0
  data_set_id = local.id_dataset
  name        = local.id_dataset
  import_mode = "SPICE"

  physical_table_map {
    physical_table_map_id = "prevision"

    relational_table {
      data_source_arn = data.terraform_remote_state.demo4[0].outputs.quicksight_fuente_arn
      schema          = "gold"
      name            = "v_prevision_vs_real"

      dynamic "input_columns" {
        for_each = local.columnas_prevision
        content {
          name = input_columns.key
          type = input_columns.value
        }
      }
    }
  }

  permissions {
    actions = [
      "quicksight:DescribeDataSet",
      "quicksight:DescribeDataSetPermissions",
      "quicksight:PassDataSet",
      "quicksight:DescribeIngestion",
      "quicksight:ListIngestions",
      "quicksight:CreateIngestion",
      "quicksight:CancelIngestion",
      "quicksight:UpdateDataSet",
      "quicksight:DeleteDataSet",
      "quicksight:UpdateDataSetPermissions",
    ]
    principal = var.quicksight_usuario_arn
  }
}
