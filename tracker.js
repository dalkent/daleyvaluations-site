/* Daley Valuations - tracker page sort + filter */
(function () {
  'use strict';

  var table = document.getElementById('tracker');
  if (!table) return;
  var tbody = table.querySelector('tbody');
  var rows = Array.from(tbody.querySelectorAll('tr'));
  var rowCount = document.getElementById('row-count');
  var totalRows = rows.length;

  var sortState = { col: null, dir: 'asc' };

  // ── Filtering ────────────────────────────────────────────────────────────────
  var sectorSelect = document.getElementById('filter-sector');
  var signalSelect = document.getElementById('filter-signal');
  var searchInput = document.getElementById('filter-search');
  var heldCheckbox = document.getElementById('filter-held');

  function applyFilter() {
    var sector = sectorSelect.value;
    var signal = signalSelect.value;
    var search = (searchInput.value || '').trim().toLowerCase();
    var heldOnly = heldCheckbox && heldCheckbox.checked;
    var visible = 0;
    rows.forEach(function (row) {
      var matchSector = !sector || row.dataset.sector === sector;
      var matchSignal = !signal || row.dataset.signal === signal;
      var matchSearch = !search ||
        row.dataset.ticker.toLowerCase().indexOf(search) !== -1 ||
        row.dataset.company.indexOf(search) !== -1;
      var matchHeld = !heldOnly || row.dataset.held === '1';
      var show = matchSector && matchSignal && matchSearch && matchHeld;
      row.classList.toggle('hidden', !show);
      if (show) visible++;
    });
    if (rowCount) {
      rowCount.textContent = visible === totalRows
        ? totalRows + ' stocks'
        : visible + ' of ' + totalRows + ' stocks';
    }
  }

  sectorSelect.addEventListener('change', applyFilter);
  signalSelect.addEventListener('change', applyFilter);
  searchInput.addEventListener('input', applyFilter);
  if (heldCheckbox) heldCheckbox.addEventListener('change', applyFilter);

  // Sector chips - click to filter by sector
  document.querySelectorAll('.sector-chip').forEach(function (chip) {
    chip.addEventListener('click', function () {
      var clickedSector = chip.dataset.sector;
      if (sectorSelect.value === clickedSector) {
        sectorSelect.value = '';
      } else {
        sectorSelect.value = clickedSector;
      }
      applyFilter();
      document.querySelectorAll('.sector-chip').forEach(function (c) {
        c.classList.toggle('active', c.dataset.sector === sectorSelect.value);
      });
      var trackerSection = document.querySelector('.tracker-section');
      if (trackerSection) trackerSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  // ── Sorting ──────────────────────────────────────────────────────────────────
  var SIGNAL_ORDER = ['Strong Buy', 'Buy', 'Fair Value', 'Sell', 'Strong Sell'];
  function signalRank(s) {
    var i = SIGNAL_ORDER.indexOf(s);
    return i === -1 ? 99 : i;
  }

  function getSortKey(row, col) {
    switch (col) {
      case 'ticker':  return row.dataset.ticker;
      case 'company': return row.dataset.company;
      case 'sector':  return row.dataset.sector;
      case 'signal':  return signalRank(row.dataset.signal);
      case 'price':   return parseFloat(row.dataset.price) || 0;
      case 'target':  return parseFloat(row.dataset.target) || 0;
      case 'vr':      return parseFloat(row.dataset.vr) || 0;
      case 'change':  return parseFloat(row.dataset.change) || 0;
      default: return '';
    }
  }

  function isNumericCol(col) {
    return col === 'price' || col === 'target' || col === 'vr' || col === 'signal' || col === 'change';
  }

  function sortBy(col) {
    if (sortState.col === col) {
      sortState.dir = sortState.dir === 'asc' ? 'desc' : 'asc';
    } else {
      sortState.col = col;
      sortState.dir = isNumericCol(col) ? 'desc' : 'asc';
    }
    var dirMul = sortState.dir === 'asc' ? 1 : -1;

    rows.sort(function (a, b) {
      var ka = getSortKey(a, col);
      var kb = getSortKey(b, col);
      if (typeof ka === 'string') return ka.localeCompare(kb) * dirMul;
      return (ka - kb) * dirMul;
    });

    rows.forEach(function (row) { tbody.appendChild(row); });

    document.querySelectorAll('th.sortable').forEach(function (th) {
      th.classList.remove('sort-asc', 'sort-desc');
      if (th.dataset.sort === col) {
        th.classList.add(sortState.dir === 'asc' ? 'sort-asc' : 'sort-desc');
      }
    });
  }

  document.querySelectorAll('th.sortable').forEach(function (th) {
    th.addEventListener('click', function () { sortBy(th.dataset.sort); });
  });

  var sectorHeader = document.querySelector('th[data-sort="sector"]');
  if (sectorHeader) sectorHeader.classList.add('sort-asc');
})();
