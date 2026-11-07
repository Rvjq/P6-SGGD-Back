# Matriz de cobertura — CAM 1.2

A tabela abaixo lista todos os 58 códigos catalogados (57 linhas originais + raiz auxiliar 4). A mesma regra pode ser aplicável a várias categorias.

| Código | Categorias | Método(s) | Situação |
|---|---|---|---|
| `1` | USF,UBT,UBT_MISTA,CAPS,UCIS,MAC,GG,SNA,SNB1 | proporcao_faixas | CALCULAVEL |
| `2` | USF,UBT,UBT_MISTA,CAPS,CECON,UCIS,MAC,GG,SNA,SNB2 | media,media_faixas | CALCULAVEL |
| `2.1` | USF,UBT,UBT_MISTA,CAPS,CECON,UCIS,MAC | proporcao_faixas | CALCULAVEL |
| `2.2` | USF,UBT,UBT_MISTA,CAPS,CECON,UCIS,MAC | faixas | CALCULAVEL |
| `2.3` | USF,UBT,UBT_MISTA,CAPS,CECON,UCIS,MAC | proporcao_faixas | CALCULAVEL |
| `2.4` | USF,UBT,UBT_MISTA,CAPS,CECON,UCIS,MAC | proporcao_faixas | CALCULAVEL |
| `3` | USF,UBT,UBT_MISTA,CAPS,CECON,UCIS,MAC,GG,SNA,SNB1,SNB2 | media,media_ponderada | CALCULAVEL,REVISAR |
| `3.I` | USF,UBT,UBT_MISTA,CAPS,CECON,UCIS,MAC | nota_informada | ENTRADA_TRATADA |
| `3.II` | USF,UBT,UBT_MISTA,CAPS,CECON,UCIS,MAC | proporcao_faixas | CALCULAVEL |
| `3.I.1` | USF,UBT,UBT_MISTA | nota_informada | ENTRADA_TRATADA |
| `3.I.2` | CAPS,CECON | faixas | CALCULAVEL |
| `3.I.3` | UCIS | faixas | CALCULAVEL |
| `3.I.4` | MAC | faixas | REVISAR |
| `4` | USF,UBT_MISTA,CAPS,UBT,UCIS,CECON,MAC,GG,SNA,SNB1,SNB2 | identidade | CALCULAVEL |
| `4.I` | USF,UBT_MISTA | indice_esf | REVISAR |
| `4.II` | CAPS | media | CALCULAVEL |
| `4.III` | UBT | media | CALCULAVEL |
| `4.IV` | UCIS | media | REVISAR |
| `4.V` | CECON | media | CALCULAVEL |
| `4.VI` | GG,SNA,SNB1,SNB2 | media | CALCULAVEL |
| `4.VII` | MAC | media | ENTRADA_TRATADA |
| `4.I.1` | USF,UBT_MISTA | meta | CALCULAVEL |
| `4.I.2` | USF,UBT_MISTA | meta | CALCULAVEL |
| `4.I.3` | USF,UBT_MISTA | meta | CALCULAVEL |
| `4.I.4` | USF,UBT_MISTA | meta | CALCULAVEL |
| `4.I.5` | USF,UBT_MISTA | meta | CALCULAVEL |
| `4.I.6` | USF,UBT_MISTA | meta | CALCULAVEL |
| `4.I.7` | USF,UBT_MISTA | meta | CALCULAVEL |
| `4.I.8` | USF,UBT_MISTA | meta | CALCULAVEL |
| `4.I.9` | USF,UBT_MISTA | meta | CALCULAVEL |
| `4.I.10` | USF,UBT_MISTA | meta | REVISAR |
| `4.I.11` | USF,UBT_MISTA | meta | CALCULAVEL |
| `4.II.1` | CAPS | meta | CALCULAVEL |
| `4.II.2` | CAPS | meta | CALCULAVEL |
| `4.II.3` | CAPS | meta | CALCULAVEL |
| `4.II.4` | CAPS | meta | CALCULAVEL |
| `4.II.5` | CAPS | meta | CALCULAVEL |
| `4.II.6` | CAPS | meta | CALCULAVEL |
| `4.III.1` | UBT | meta | CALCULAVEL |
| `4.III.2` | UBT | meta | CALCULAVEL |
| `4.IV.1` | UCIS | meta | REVISAR |
| `4.IV.2` | UCIS | nao_configurado | REVISAR |
| `4.V.1` | CECON | meta | CALCULAVEL |
| `4.V.2` | CECON | meta | CALCULAVEL |
| `4.V.3` | CECON | meta | CALCULAVEL |
| `4.V.4` | CECON | meta | CALCULAVEL |
| `4.V.5` | CECON | meta | CALCULAVEL |
| `4.VII.1.1` | MAC | meta | CALCULAVEL |
| `4.VII.1.2` | MAC | meta | CALCULAVEL |
| `4.VII.1.3` | MAC | meta | CALCULAVEL |
| `4.VII.2.1` | MAC | meta | CALCULAVEL |
| `4.VII.2.2` | MAC | nao_configurado | REVISAR |
| `4.VII.3.1` | MAC | faixas | CALCULAVEL |
| `4.VII.3.2` | MAC | faixas | CALCULAVEL |
| `5` | GG,SNA,SNB1 | media | CALCULAVEL |
| `5.I` | GG,SNA,SNB1 | meta | CALCULAVEL |
| `5.II` | GG,SNA,SNB1 | meta | CALCULAVEL |
| `5.III` | GG,SNA,SNB1 | meta | REVISAR |

## Interpretação dos estados

- **CALCULAVEL:** há um método computacional explícito para os dados já aferidos; ainda depende de Coleta, validação e fonte adequada.
- **ENTRADA_TRATADA:** requer nota previamente apurada externamente (por exemplo ASU a partir dos questionários).
- **REVISAR:** discrepância, ambiguidade ou regra incompleta; o motor bloqueia cálculo automático.

## Controle da abrangência

- 58 códigos distintos; 157 associações por categoria.
- Distribuição de associações por status: {'CALCULAVEL': 127, 'REVISAR': 19, 'ENTRADA_TRATADA': 11}.
- 44 pesos principais permanecem intactos.
- Nenhuma regra técnica da documentação parcial de CAM 2.0 foi assumida.
