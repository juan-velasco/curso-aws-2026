-- Una fila por país, familia, día previsto y fecha de cálculo
CREATE TABLE IF NOT EXISTS gold.fct_prevision (
  fecha_calculo      DATE NOT NULL,
  fecha_sk           INT NOT NULL,
  pais               VARCHAR(2) NOT NULL,
  familia            VARCHAR(30) NOT NULL,
  unidades_previstas DECIMAL(12,2)
) DISTSTYLE ALL SORTKEY (fecha_calculo, fecha_sk);

GRANT SELECT ON gold.fct_prevision TO ROLE lector_gold_completo;
