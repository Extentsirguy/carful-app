import React, { useState, useCallback, useRef } from 'react';
import { Upload, File, X, AlertCircle } from 'lucide-react';

function FileDropZone({ onFileSelect, accept = '.csv', maxSize = 100 * 1024 * 1024 }) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  const validateFile = useCallback(
    (file) => {
      // Check file extension
      const ext = file.name.split('.').pop().toLowerCase();
      const acceptedExts = accept.split(',').map((a) => a.trim().replace('.', ''));
      if (!acceptedExts.includes(ext)) {
        return `Invalid file type. Accepted: ${accept}`;
      }

      // Check file size
      if (file.size > maxSize) {
        return `File too large. Maximum: ${(maxSize / (1024 * 1024)).toFixed(0)}MB`;
      }

      return null;
    },
    [accept, maxSize]
  );

  const handleFile = useCallback(
    (file) => {
      setError(null);
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }
      onFileSelect(file);
    },
    [onFileSelect, validateFile]
  );

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        handleFile(files[0]);
      }
    },
    [handleFile]
  );

  const handleInputChange = useCallback(
    (e) => {
      const files = Array.from(e.target.files);
      if (files.length > 0) {
        handleFile(files[0]);
      }
    },
    [handleFile]
  );

  const handleClick = useCallback(() => {
    inputRef.current?.click();
  }, []);

  return (
    <div className="space-y-3">
      <div
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          relative border-2 border-dashed rounded-xl p-10
          flex flex-col items-center justify-center gap-4
          cursor-pointer transition-all duration-200
          ${
            isDragging
              ? 'border-carful-500 bg-carful-50'
              : 'border-slate-300 hover:border-carful-400 hover:bg-slate-50'
          }
          ${error ? 'border-error-500 bg-error-50' : ''}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleInputChange}
          className="hidden"
        />

        <div
          className={`
          p-4 rounded-full transition-colors
          ${isDragging ? 'bg-carful-100' : 'bg-slate-100'}
        `}
        >
          <Upload
            className={`w-8 h-8 ${isDragging ? 'text-carful-600' : 'text-slate-400'}`}
          />
        </div>

        <div className="text-center">
          <p className="text-lg font-medium text-slate-700">
            {isDragging ? 'Drop your file here' : 'Drag and drop your CSV file here'}
          </p>
          <p className="text-sm text-slate-500 mt-1">or click to browse</p>
        </div>

        <p className="text-xs text-slate-400">
          Accepted: {accept} • Max size: {(maxSize / (1024 * 1024)).toFixed(0)}MB
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-error-50 text-error-600">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}
    </div>
  );
}

// File preview component
export function FilePreview({ file, onRemove }) {
  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="flex items-center gap-3 p-4 bg-slate-50 rounded-lg border border-slate-200">
      <div className="p-2 bg-carful-100 rounded-lg">
        <File className="w-6 h-6 text-carful-600" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-slate-900 truncate">{file.name}</p>
        <p className="text-sm text-slate-500">{formatSize(file.size)}</p>
      </div>
      {onRemove && (
        <button
          onClick={onRemove}
          className="p-1 hover:bg-slate-200 rounded-full transition-colors"
          title="Remove file"
        >
          <X className="w-5 h-5 text-slate-500" />
        </button>
      )}
    </div>
  );
}

export default FileDropZone;
