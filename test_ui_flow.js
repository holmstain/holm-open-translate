// Run with node --test test_ui_flow.js. Execute the real submission handler.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup() {
    const elements = {};
    function element() { return {style: {}, dataset: {}, innerHTML: 'Translate', textContent: '', disabled: false,
        setAttribute(name, value) { this[name] = value; }, removeAttribute(name) { delete this[name]; },
        appendChild() {}, click() {}, remove() {}, focus() {}}; }
    for (const id of ['translate-btn','progress-wrap','progress-bar','progress-percent','progress-status','progress-label','progress-success','progress-success-text']) elements[id] = element();
    elements['progress-success'].style.display = 'none';
    const form = element();
    form.addEventListener = (_, handler) => form.submitHandler = handler;
    form.querySelectorAll = () => [];
    let resolveFetch;
    let calls = 0;
    const context = {document: {querySelector: () => form, getElementById: id => elements[id], createElement: element, body: element()},
        translations: {tr: {progressWaiting:'Waiting', progressPreparing: 'Preparing', progressTranslating: 'Translating', progressDone:'Done', download:'Download'}}, languageSelect: {value:'tr'},
        FormData: function () {}, URL: {createObjectURL: () => 'blob:archive', revokeObjectURL() {}},
        fetch: () => { calls++; return new Promise(resolve => resolveFetch = resolve); },
        requestAnimationFrame() {}, setTimeout() {}, console};
    const source = fs.readFileSync('app.py', 'utf8');
    const start = source.lastIndexOf('(function () {');
    const end = source.indexOf('})();', start) + 5;
    vm.runInNewContext(source.slice(start, end), context);
    return {elements, form, submit: () => form.submitHandler({preventDefault(){}}), calls: () => calls,
        respond: result => resolveFetch(result)};
}

test('request starts immediately and stays busy until ZIP response', async () => {
    const ui = setup();
    const pending = ui.submit();
    assert.equal(ui.calls(), 1);
    assert.equal(ui.elements['translate-btn'].disabled, true);
    assert.equal(ui.elements['progress-success'].style.display, 'none');
    ui.respond({ok:true, headers:{get: name => name === 'Content-Type' ? 'application/zip' : 'attachment; filename=translation.zip'}, blob:async () => ({})});
    await pending;
    assert.equal(ui.elements['translate-btn'].disabled, false);
    assert.equal(ui.elements['progress-success'].style.display, 'flex');
});

test('HTTP error retains form and allows retry without claiming success', async () => {
    const ui = setup();
    const pending = ui.submit();
    assert.equal(ui.calls(), 1);
    ui.respond({ok:false, text:async () => 'Correct the source language and retry.'});
    await pending;
    assert.equal(ui.elements['translate-btn'].disabled, false);
    assert.equal(ui.elements['progress-success'].style.display, 'none');
    assert.match(ui.elements['progress-status'].textContent, /Correct the source language/);
});

function setupTheme(initialTheme = 'light') {
    const source = fs.readFileSync('app.py', 'utf8');
    const button = source.match(/<button[^>]*id="theme-toggle"[^>]*>/)?.[0];
    assert.ok(button);
    assert.doesNotMatch(button, /data-i18n=/); // Locale updates must retain the emoji element.

    const handlers = {};
    const attributes = {};
    const themeToggle = {
        setAttribute(name, value) { attributes[name] = value; },
        addEventListener(name, handler) { handlers[name] = handler; },
    };
    const languageSelect = {
        value: 'tr',
        setAttribute() {},
        addEventListener() {},
    };
    const themeLabel = {textContent: ''};
    const themeEmoji = {textContent: ''};
    const meta = {content: ''};
    const stored = {};
    const nodes = {'interface-language': languageSelect, 'theme-toggle': themeToggle,
        'theme-label': themeLabel, 'theme-emoji': themeEmoji};
    const document = {
        documentElement: {dataset: {theme: initialTheme}},
        getElementById: id => nodes[id],
        querySelectorAll: () => [],
        querySelector: () => meta,
        title: '',
    };
    const translations = {tr: {pageTitle: 'Çeviri', interfaceLanguage: 'Arayüz dili',
        themeDark: 'Koyu temayı aç', themeLight: 'Açık temayı aç'},
        en: {pageTitle: 'Translate', interfaceLanguage: 'Interface language',
            themeDark: 'Open dark theme', themeLight: 'Open light theme'}};
    const start = source.indexOf('const translations = {{');
    const end = source.indexOf('/* Request feedback', start);
    assert.ok(start >= 0 && end > start);
    const script = source.slice(start, end).replace(
        'const translations = {{ locales | tojson | safe }};',
        `const translations = ${JSON.stringify(translations)};`
    );
    vm.runInNewContext(script, {document, navigator: {languages: ['tr']},
        localStorage: {getItem: key => stored[key] || null, setItem: (key, value) => stored[key] = value}});
    return {document, themeToggle, themeLabel, themeEmoji, attributes, meta, stored,
        click: () => handlers.click()};
}

test('theme emoji and accessible label follow the selected theme', () => {
    const ui = setupTheme();
    assert.equal(ui.themeEmoji.textContent, '🌙');
    assert.equal(ui.attributes['aria-label'], 'Koyu temayı aç');
    assert.equal(ui.attributes['aria-pressed'], 'false');
    ui.click();
    assert.equal(ui.document.documentElement.dataset.theme, 'dark');
    assert.equal(ui.themeEmoji.textContent, '☀️');
    assert.equal(ui.attributes['aria-label'], 'Açık temayı aç');
    assert.equal(ui.attributes['aria-pressed'], 'true');
    assert.equal(ui.stored['holm-theme'], 'dark');
    ui.click();
    assert.equal(ui.themeEmoji.textContent, '🌙');
    assert.equal(ui.stored['holm-theme'], 'light');

    const savedDark = setupTheme('dark');
    assert.equal(savedDark.themeEmoji.textContent, '☀️');
    assert.equal(savedDark.meta.content, '#111a2b');
});
