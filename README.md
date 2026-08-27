<div align="center">

# 🚀 my_megasource_scrapers

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Stremio](https://img.shields.io/badge/Stremio-Addon-purple?style=for-the-badge&logo=stremio&logoColor=white)](https://www.stremio.com/)

<p align="center">
  <b>Scrapers customizados em Python desenvolvidos para o addon MegaSource (Stremio / Nuvio).</b>
</p>

</div>

---

## 📌 Sobre o Projeto

Este repositório reúne os motores de extração (*scrapers*) criados para alimentar o addon **MegaSource**. Cada módulo é responsável por consultar provedores de conteúdo nacionais, extrair links de reprodução (embeds ou magnets) e retorná-los no contrato aceito pelo motor do MegaSource.

---

## 🏗️ Estrutura da Função (`get_streams`)

Todos os scrapers deste repositório seguem rigorosamente a assinatura padrão exigida pelo MegaSource:

```python
def get_streams(media_type: str, media_id: str, config: dict = None) -> list:
    """
    Parâmetros:
        media_type (str): Tipo de mídia ('movie' ou 'series')
        media_id (str): ID do IMDb (ex: 'tt1877830')
        config (dict, optional): Configurações repassadas pelo addon
        
    Retorna:
        list: Lista de dicionários no formato {'name', 'title', 'url', 'quality'}
    """
