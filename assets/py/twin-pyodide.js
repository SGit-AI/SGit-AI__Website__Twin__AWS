/* aws.twin.sgit.ai — load Python into the page, with the twin in it.

   One loader for every page that runs the Python twin: Pyodide (pinned), the two
   standard-library packages Pyodide keeps out of its default build that botocore needs
   (ssl and hashlib), boto3, OSBot-Utils and OSBot-AWS from PyPI (pinned), then this
   site's own aws_twin package and its tests, unpacked from assets/py/aws_twin.zip.

   The page's own code never calls AWS or the twin directly: it calls Python functions,
   which call boto3 or OSBot-AWS, which the twin answers. The same Python runs in CI.

   Third-party fetches, stated: cdn.jsdelivr.net (Pyodide), pypi.org and
   files.pythonhosted.org (the wheels). Nothing else leaves the page. */
(function (root) {
  'use strict';
  var PYODIDE_VERSION = '0.28.3';
  var PACKAGES = ['boto3==1.43.116', 'botocore==1.43.116', 'osbot-utils==3.75.0', 'osbot-aws==2.39.10'];

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      if (root.loadPyodide) return resolve();
      var s = document.createElement('script');
      s.src = src; s.onload = resolve; s.onerror = function () { reject(new Error('could not load ' + src)); };
      document.head.appendChild(s);
    });
  }

  /* opts: { bundleUrl, packages, onStep(name, ms) }  →  Promise<pyodide> */
  function loadTwinPython(opts) {
    opts = opts || {};
    var step = opts.onStep || function () {};
    var t0 = performance.now(), t = t0, timings = {};
    var mark = function (name) { var now = performance.now(); timings[name] = Math.round(now - t); t = now; step(name, timings[name]); };
    var indexURL = 'https://cdn.jsdelivr.net/pyodide/v' + PYODIDE_VERSION + '/full/';
    var py;
    return loadScript(indexURL + 'pyodide.js')
      .then(function () { return root.loadPyodide({ indexURL: indexURL }); })
      .then(function (p) { py = p; mark('pyodide'); return py.loadPackage(['ssl', 'hashlib', 'micropip']); })
      .then(function () { mark('stdlib'); return py.pyimport('micropip').install(opts.packages || PACKAGES); })
      .then(function () { mark('wheels'); return fetch(opts.bundleUrl || '../assets/py/aws_twin.zip'); })
      .then(function (r) { if (!r.ok) throw new Error('bundle: HTTP ' + r.status); return r.arrayBuffer(); })
      .then(function (buf) {
        py.unpackArchive(buf, 'zip', { extractDir: '/home/pyodide/site' });
        py.runPython('import sys; sys.path.insert(0, "/home/pyodide/site")');
        mark('bundle');
        py.twinTimings = timings; py.twinTimings.total = Math.round(performance.now() - t0);
        return py;
      });
  }

  root.loadTwinPython = loadTwinPython;
  root.TWIN_PY_PACKAGES = PACKAGES;
  root.TWIN_PYODIDE_VERSION = PYODIDE_VERSION;
}(typeof self !== 'undefined' ? self : this));
