import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import Papa from 'papaparse';
import { 
  ArrowLeft, 
  Upload, 
  FileSpreadsheet, 
  Building2, 
  CheckCircle, 
  XCircle, 
  RefreshCw,
  Download,
  AlertTriangle,
  HelpCircle,
  Trash2,
  Plus
} from 'lucide-react';

const BulkPropertyImportPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [parsedData, setParsedData] = useState([]);
  const [errors, setErrors] = useState([]);
  const [importing, setImporting] = useState(false);
  const [importResults, setImportResults] = useState(null);
  const [fileName, setFileName] = useState('');

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setFileName(file.name);
    setErrors([]);
    setImportResults(null);

    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        const { data, errors: parseErrors } = results;
        
        if (parseErrors.length > 0) {
          setErrors(parseErrors.map(e => ({ row: e.row, error: e.message })));
          return;
        }

        // Validate and map data
        const validationErrors = [];
        const mappedData = data.map((row, idx) => {
          const mapped = {
            address_line_1: row.address_line_1 || row.address || row.Address || row['Address Line 1'] || '',
            address_line_2: row.address_line_2 || row['Address Line 2'] || '',
            city: row.city || row.City || row.town || row.Town || '',
            postcode: row.postcode || row.Postcode || row['Post Code'] || row.zip || '',
            property_type: (row.property_type || row.type || row.Type || 'residential').toLowerCase(),
            number_of_units: parseInt(row.number_of_units || row.units || row.Units || '1', 10) || 1,
            _rowIndex: idx + 2 // +2 for header row and 0-indexing
          };

          // Validation
          if (!mapped.address_line_1) {
            validationErrors.push({ row: mapped._rowIndex, error: 'Missing address' });
          }
          if (!mapped.city) {
            validationErrors.push({ row: mapped._rowIndex, error: 'Missing city' });
          }
          if (!mapped.postcode) {
            validationErrors.push({ row: mapped._rowIndex, error: 'Missing postcode' });
          }

          return mapped;
        });

        setErrors(validationErrors);
        setParsedData(mappedData);
        
        if (validationErrors.length === 0) {
          toast.success(`Parsed ${mappedData.length} properties from CSV`);
        } else {
          toast.warning(`Found ${validationErrors.length} validation errors`);
        }
      },
      error: (error) => {
        toast.error('Failed to parse CSV file');
        setErrors([{ row: 0, error: error.message }]);
      }
    });
  };

  const removeProperty = (index) => {
    setParsedData(prev => prev.filter((_, i) => i !== index));
  };

  const handleImport = async () => {
    if (parsedData.length === 0) {
      toast.error('No properties to import');
      return;
    }

    // Check for validation errors
    const hasErrors = errors.filter(e => 
      parsedData.some(p => p._rowIndex === e.row)
    ).length > 0;

    if (hasErrors) {
      toast.error('Please fix validation errors before importing');
      return;
    }

    setImporting(true);

    try {
      // Prepare data (remove _rowIndex)
      const properties = parsedData.map(({ _rowIndex, ...rest }) => rest);

      const response = await api.post('/properties/bulk-import', { properties });
      
      setImportResults(response.data.summary);
      
      if (response.data.summary.failed === 0) {
        toast.success(`Successfully imported ${response.data.summary.successful} properties!`);
      } else {
        toast.warning(
          `Imported ${response.data.summary.successful} of ${response.data.summary.total} properties`
        );
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  const downloadTemplate = () => {
    const template = `address_line_1,address_line_2,city,postcode,property_type,number_of_units
123 Main Street,Flat 1,London,SW1A 1AA,residential,1
456 High Street,,Manchester,M1 1AA,hmo,4
789 Park Road,Unit 2B,Birmingham,B1 1AA,commercial,2`;
    
    const blob = new Blob([template], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'property_import_template.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    
    toast.success('Template downloaded');
  };

  const clearAll = () => {
    setParsedData([]);
    setErrors([]);
    setImportResults(null);
    setFileName('');
  };

  return (
    <div className="min-h-screen bg-gray-50" data-testid="bulk-property-import-page">
      {/* Header */}
      <header className="bg-midnight-blue text-white py-4">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button 
                onClick={() => navigate('/app/dashboard')} 
                className="text-gray-300 hover:text-white"
                data-testid="back-btn"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <h1 className="text-xl font-bold">Bulk Property Import</h1>
                <p className="text-sm text-gray-300">Import multiple properties from a CSV file</p>
              </div>
            </div>
            <Button
              variant="outline"
              onClick={downloadTemplate}
              className="bg-transparent border-white/30 text-white hover:bg-white/10"
              data-testid="download-template-btn"
            >
              <Download className="w-4 h-4 mr-2" />
              Download Template
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Upload Section */}
        <Card className="mb-6" data-testid="upload-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5" />
              Upload CSV File
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div 
              className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-electric-teal transition-colors"
            >
              <input
                type="file"
                accept=".csv"
                onChange={handleFileUpload}
                className="hidden"
                id="csv-upload"
                data-testid="csv-file-input"
              />
              <label htmlFor="csv-upload" className="cursor-pointer">
                <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-lg font-medium text-midnight-blue mb-2">
                  {fileName ? fileName : 'Click to upload CSV file'}
                </p>
                <p className="text-sm text-gray-500">
                  or drag and drop your file here
                </p>
              </label>
            </div>

            {/* Column Mapping Help */}
            <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <div className="flex items-start gap-2">
                <HelpCircle className="w-5 h-5 text-blue-600 mt-0.5" />
                <div className="text-sm text-blue-700">
                  <p className="font-medium mb-1">Expected CSV Columns:</p>
                  <ul className="list-disc list-inside space-y-1 text-blue-600">
                    <li><strong>address_line_1</strong> (required) - Street address</li>
                    <li><strong>address_line_2</strong> (optional) - Flat/unit number</li>
                    <li><strong>city</strong> (required) - Town/city name</li>
                    <li><strong>postcode</strong> (required) - UK postcode</li>
                    <li><strong>property_type</strong> (optional) - residential, hmo, commercial</li>
                    <li><strong>number_of_units</strong> (optional) - Number of units (default: 1)</li>
                  </ul>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Validation Errors */}
        {errors.length > 0 && (
          <Card className="mb-6 border-red-200" data-testid="validation-errors-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-red-600">
                <AlertTriangle className="w-5 h-5" />
                Validation Errors ({errors.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {errors.map((error, idx) => (
                  <div key={idx} className="text-sm text-red-600 flex items-center gap-2">
                    <XCircle className="w-4 h-4" />
                    Row {error.row}: {error.error}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Parsed Data Preview */}
        {parsedData.length > 0 && (
          <Card className="mb-6" data-testid="preview-card">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="w-5 h-5" />
                  Properties to Import ({parsedData.length})
                </CardTitle>
                <Button variant="ghost" size="sm" onClick={clearAll} data-testid="clear-all-btn">
                  <Trash2 className="w-4 h-4 mr-1" />
                  Clear All
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="preview-table">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium text-gray-600">#</th>
                      <th className="px-3 py-2 text-left font-medium text-gray-600">Address</th>
                      <th className="px-3 py-2 text-left font-medium text-gray-600">City</th>
                      <th className="px-3 py-2 text-left font-medium text-gray-600">Postcode</th>
                      <th className="px-3 py-2 text-left font-medium text-gray-600">Type</th>
                      <th className="px-3 py-2 text-left font-medium text-gray-600">Units</th>
                      <th className="px-3 py-2 text-center font-medium text-gray-600">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {parsedData.map((prop, idx) => {
                      const hasError = errors.some(e => e.row === prop._rowIndex);
                      return (
                        <tr 
                          key={idx} 
                          className={hasError ? 'bg-red-50' : ''}
                          data-testid={`row-${idx}`}
                        >
                          <td className="px-3 py-2 text-gray-500">{idx + 1}</td>
                          <td className="px-3 py-2">
                            {prop.address_line_1}
                            {prop.address_line_2 && <span className="text-gray-400">, {prop.address_line_2}</span>}
                          </td>
                          <td className="px-3 py-2">{prop.city || <span className="text-red-500">Missing</span>}</td>
                          <td className="px-3 py-2">{prop.postcode || <span className="text-red-500">Missing</span>}</td>
                          <td className="px-3 py-2 capitalize">{prop.property_type}</td>
                          <td className="px-3 py-2">{prop.number_of_units}</td>
                          <td className="px-3 py-2 text-center">
                            <button
                              onClick={() => removeProperty(idx)}
                              className="text-red-500 hover:text-red-700"
                              data-testid={`remove-${idx}`}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Import Results */}
        {importResults && (
          <Card className="mb-6 border-2 border-green-200" data-testid="results-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-green-700">
                <CheckCircle className="w-5 h-5" />
                Import Complete
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4 text-center mb-6">
                <div>
                  <div className="text-2xl font-bold text-midnight-blue">{importResults.total}</div>
                  <div className="text-sm text-gray-500">Total</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-green-600">{importResults.successful}</div>
                  <div className="text-sm text-gray-500">Successful</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-red-600">{importResults.failed}</div>
                  <div className="text-sm text-gray-500">Failed</div>
                </div>
              </div>
              
              {importResults.errors?.length > 0 && (
                <div className="mb-4">
                  <h4 className="font-medium text-red-600 mb-2">Failed Imports:</h4>
                  <div className="space-y-1 max-h-32 overflow-y-auto text-sm">
                    {importResults.errors.map((err, idx) => (
                      <div key={idx} className="text-red-600">
                        Row {err.row}: {err.error} {err.address && `(${err.address})`}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {importResults.created_properties?.length > 0 && (
                <div className="mb-4">
                  <h4 className="font-medium text-green-600 mb-2">Created Properties:</h4>
                  <div className="space-y-1 max-h-32 overflow-y-auto text-sm">
                    {importResults.created_properties.slice(0, 5).map((prop, idx) => (
                      <div key={idx} className="text-green-700">
                        ✓ {prop.address} ({prop.requirements_created} requirements)
                      </div>
                    ))}
                    {importResults.created_properties.length > 5 && (
                      <div className="text-gray-500">
                        ...and {importResults.created_properties.length - 5} more
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              <div className="flex gap-3">
                <Button onClick={() => navigate('/app/dashboard')} className="flex-1" data-testid="view-dashboard-btn">
                  View Dashboard
                </Button>
                <Button variant="outline" onClick={clearAll} data-testid="import-more-btn">
                  Import More
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Import Button */}
        {parsedData.length > 0 && !importResults && (
          <Button
            onClick={handleImport}
            disabled={importing || errors.length > 0}
            className="w-full py-6 text-lg"
            data-testid="import-btn"
          >
            {importing ? (
              <>
                <RefreshCw className="w-5 h-5 animate-spin mr-2" />
                Importing...
              </>
            ) : (
              <>
                <Plus className="w-5 h-5 mr-2" />
                Import {parsedData.length} Properties
              </>
            )}
          </Button>
        )}
      </main>
    </div>
  );
};

export default BulkPropertyImportPage;
