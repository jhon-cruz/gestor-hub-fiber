# Fork e atualização do FiberQ

## Repositórios

- Upstream oficial: `https://github.com/vukovicvl/fiberq.git`
- Fork do projeto: `https://github.com/jhon-cruz/fiberq.git`
- Produto: `https://github.com/jhon-cruz/gestor-hub-fiber.git`

O FiberQ é incluído em `vendor/fiberq` como submódulo para preservar histórico, licença e uma fronteira clara entre upstream e código próprio. A versão inicial está fixada na tag `v1.4.0`, commit `07b8c12a628a5cc9641569ba3f8ca9ef867ce696`.

Enquanto a criação do fork estiver pendente, o submódulo aponta diretamente para o upstream oficial. Depois da criação, atualizar `.gitmodules` para o fork e manter dentro dele:

```bash
git remote rename origin fork
git remote add upstream https://github.com/vukovicvl/fiberq.git
git fetch upstream --tags
```

## Política de mudanças

1. Implementar domínio e integrações no Gestor Hub Fiber.
2. Alterar FiberQ somente quando uma extensão externa não for suficiente.
3. Criar branch própria no fork para cada mudança.
4. Registrar origem, razão e data da modificação.
5. Manter LICENSE, notices e GPL-3.0-or-later.
6. Executar testes upstream em QGIS 3/Qt5 e QGIS 4/Qt6 antes de atualizar o ponteiro do submódulo.

## Atualização a partir do upstream

Dentro de uma cópia de trabalho do fork:

```bash
git fetch upstream --tags
git checkout main
git merge --ff-only upstream/main
git push fork main
```

Se houver mudanças próprias que impeçam fast-forward, usar uma branch de integração, resolver conflitos, executar a matriz completa e abrir pull request no fork. Nunca forçar atualização de `main` sem revisão.
