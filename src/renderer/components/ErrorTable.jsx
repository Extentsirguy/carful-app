import React, { useState, useMemo } from 'react';
import { ChevronUp, ChevronDown, Search, ExternalLink } from 'lucide-react';
import ErrorDetail from './ErrorDetail';

function ErrorTable({ errors, onSelectError, pageSize = 10 }) {
  const [sortField, setSortField] = useState('row');
  const [sortDirection, setSortDirection] = useState('asc');
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedError, setSelectedError] = useState(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  // Filter and sort errors
  const filteredErrors = useMemo(() => {
    let result = [...errors];

    // Filter by search term
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      result = result.filter(
        (e) =>
          e.tin?.toLowerCase().includes(term) ||
          e.country?.toLowerCase().includes(term) ||
          e.message?.toLowerCase().includes(term) ||
          String(e.row).includes(term)
      );
    }

    // Sort
    result.sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];

      // Handle numeric fields
      if (sortField === 'row') {
        aVal = Number(aVal) || 0;
        bVal = Number(bVal) || 0;
      }

      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    return result;
  }, [errors, searchTerm, sortField, sortDirection]);

  // Paginate
  const totalPages = Math.ceil(filteredErrors.length / pageSize);
  const paginatedErrors = filteredErrors.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const handleErrorSelect = (error) => {
    setSelectedError(error);
    setIsDetailOpen(true);
    onSelectError?.(error);
  };

  const SortIcon = ({ field }) => {
    if (sortField !== field) return null;
    return sortDirection === 'asc' ? (
      <ChevronUp className="w-4 h-4" />
    ) : (
      <ChevronDown className="w-4 h-4" />
    );
  };

  const columns = [
    { id: 'row', label: 'Row', width: 'w-20' },
    { id: 'tin', label: 'TIN', width: 'w-36' },
    { id: 'country', label: 'Country', width: 'w-24' },
    { id: 'message', label: 'Error Message', width: 'flex-1' },
  ];

  if (errors.length === 0) {
    return (
      <div className="text-center py-8 text-slate-500">
        No validation errors found.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            setCurrentPage(1);
          }}
          placeholder="Search errors..."
          className="input pl-10"
        />
      </div>

      {/* Table */}
      <div className="overflow-x-auto border border-slate-200 rounded-lg">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              {columns.map((col) => (
                <th
                  key={col.id}
                  onClick={() => handleSort(col.id)}
                  className={`
                    px-4 py-3 text-left font-medium text-slate-600
                    cursor-pointer hover:bg-slate-100 transition-colors
                    ${col.width}
                  `}
                >
                  <div className="flex items-center gap-1">
                    {col.label}
                    <SortIcon field={col.id} />
                  </div>
                </th>
              ))}
              <th className="w-12"></th>
            </tr>
          </thead>
          <tbody>
            {paginatedErrors.map((error, idx) => (
              <tr
                key={`${error.row}-${idx}`}
                className="border-b border-slate-100 hover:bg-slate-50 transition-colors"
              >
                <td className="px-4 py-3 font-mono text-slate-600">{error.row}</td>
                <td className="px-4 py-3 font-mono text-slate-900">{error.tin || '—'}</td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-700">
                    {error.country || '—'}
                  </span>
                </td>
                <td className="px-4 py-3 text-error-600">{error.message}</td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleErrorSelect(error)}
                    className="p-1 hover:bg-slate-200 rounded transition-colors"
                    title="View details"
                  >
                    <ExternalLink className="w-4 h-4 text-slate-400" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-500">
            Showing {(currentPage - 1) * pageSize + 1} to{' '}
            {Math.min(currentPage * pageSize, filteredErrors.length)} of{' '}
            {filteredErrors.length} errors
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="btn btn-secondary py-1 px-3 text-sm"
            >
              Previous
            </button>
            <span className="text-sm text-slate-600">
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="btn btn-secondary py-1 px-3 text-sm"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Error Detail Modal */}
      <ErrorDetail
        error={selectedError}
        csvRowData={selectedError?.csvRowData}
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
      />
    </div>
  );
}

export default ErrorTable;
