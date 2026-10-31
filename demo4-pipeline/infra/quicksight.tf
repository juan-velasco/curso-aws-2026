# La suscripción de QuickSight es manual y previa: todo esto va detrás de quicksight_activo.
# Análisis y dashboard se crean a mano en clase (GUION.md).

locals {
  id_dataset = "ventas_dashboard"

  columnas_dashboard = {
    fecha        = "DATETIME"
    fecha_sk     = "INTEGER"
    anio         = "INTEGER"
    semana_iso   = "INTEGER"
    mes          = "INTEGER"
    es_rebajas   = "BIT"
    pais         = "STRING"
    region       = "STRING"
    tienda_id    = "STRING"
    familia      = "STRING"
    color        = "STRING"
    talla        = "STRING"
    segmento     = "STRING"
    clave_ticket = "STRING"
    unidades     = "INTEGER"
    venta_neta   = "DECIMAL"
  }

  acciones_fuente = [
    "quicksight:DescribeDataSource",
    "quicksight:DescribeDataSourcePermissions",
    "quicksight:PassDataSource",
    "quicksight:UpdateDataSource",
    "quicksight:DeleteDataSource",
    "quicksight:UpdateDataSourcePermissions",
  ]

  acciones_dataset = [
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
}

resource "aws_quicksight_data_source" "gold" {
  count          = var.quicksight_activo ? 1 : 0
  data_source_id = "curso-redshift-gold"
  name           = "curso-redshift-gold"
  type           = "REDSHIFT"

  parameters {
    redshift {
      host     = aws_redshiftserverless_workgroup.hp_retail.endpoint[0].address
      port     = aws_redshiftserverless_workgroup.hp_retail.endpoint[0].port
      database = "dev"
    }
  }

  credentials {
    credential_pair {
      username = "quicksight_ro"
      password = random_password.quicksight_ro.result
    }
  }

  ssl_properties {
    disable_ssl = false
  }

  permission {
    actions   = local.acciones_fuente
    principal = var.quicksight_usuario_arn
  }
}

resource "aws_quicksight_data_set" "ventas" {
  count       = var.quicksight_activo ? 1 : 0
  data_set_id = local.id_dataset
  name        = local.id_dataset
  import_mode = "SPICE"

  physical_table_map {
    physical_table_map_id = "ventas"

    relational_table {
      data_source_arn = aws_quicksight_data_source.gold[0].arn
      schema          = "gold"
      name            = "v_dashboard_ventas"

      dynamic "input_columns" {
        for_each = local.columnas_dashboard
        content {
          name = input_columns.key
          type = input_columns.value
        }
      }
    }
  }

  logical_table_map {
    logical_table_map_id = "ventas"
    alias                = "ventas"

    source {
      physical_table_id = "ventas"
    }

    # Los agregados se crean en el análisis; aquí, solo los campos calculados de fila
    data_transforms {
      create_columns_operation {
        columns {
          column_id   = "venta_rebajas"
          column_name = "venta_rebajas"
          expression  = "ifelse({es_rebajas} = 1, {venta_neta}, 0.0)"
        }
      }
    }
  }

  permissions {
    actions   = local.acciones_dataset
    principal = var.quicksight_usuario_arn
  }
}
