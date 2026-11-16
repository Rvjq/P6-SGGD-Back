"""Regressão: impedir que a rota da dashboard volte a retornar 404 por URL ausente."""
from django.test import SimpleTestCase
from django.urls import resolve, reverse


class RotaPainelConfiguradorTests(SimpleTestCase):
    def test_rota_registrada_no_projeto(self):
        url = "/api/coleta/painel-configurador/"
        self.assertEqual(reverse("painel-configurador"), url)
        self.assertEqual(resolve(url).view_name, "painel-configurador")
