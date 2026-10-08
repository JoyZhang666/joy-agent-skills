// The supplied legacy publisher cannot safely satisfy the current release contract.
// Explicitly block instead of silently ignoring article-dir, cover or confirmations.
console.error('Word 自动上传暂不可用：请检查本地预览后在公众号后台手动导入。此入口不读取凭据、不联网、不上传；SKIP_COVER 不能绕过。普通单图 Markdown 请使用 scripts/push_guarded.py 的独立流程。');
process.exitCode=2;
