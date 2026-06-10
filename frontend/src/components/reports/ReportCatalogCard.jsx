import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Download, RefreshCw, ArrowUpRight } from 'lucide-react';
import { cn } from '../../lib/utils';
import {
  FORMAT_GUIDANCE,
  reportCardTierClass,
} from '../../utils/reportCatalogPresentation';

/**
 * Governed report catalog card — purpose, audience, export grade, best-used-for.
 */
export default function ReportCatalogCard({
  report,
  icon,
  selectedFormat,
  generating,
  onDownload,
  specialtyAction,
  className,
}) {
  const pres = report.presentation || {};
  const tier = reportCardTierClass(pres.ecosystemGroup);
  const bestUsed = (pres.bestUsedFor || []).slice(0, 3);
  const formats = report.formats || [];
  const formatHint = FORMAT_GUIDANCE[selectedFormat];

  return (
    <Card
      className={cn('transition-shadow hover:shadow-md', tier, className)}
      data-testid={`report-card-${report.id}`}
      data-report-tier={pres.ecosystemGroup || 'default'}
    >
      <CardContent className="p-5">
        <div className="flex items-start gap-3">
          {icon ? <div className="p-2.5 bg-gray-50 rounded-lg shrink-0">{icon}</div> : null}
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h3 className="font-semibold text-midnight-blue text-base leading-snug">{report.name}</h3>
              {report.displayExportGrade ? (
                <span
                  className="text-[11px] uppercase tracking-wide text-gray-500 border border-gray-200 rounded px-1.5 py-0.5 font-medium"
                  data-testid={`report-grade-${report.id}`}
                >
                  {report.displayExportGrade}
                </span>
              ) : null}
            </div>
            <p className="text-sm text-gray-700 leading-relaxed">{report.description}</p>
            {pres.audience ? (
              <p className="text-xs text-gray-500 mt-2">
                <span className="font-medium text-gray-600">Audience:</span> {pres.audience}
              </p>
            ) : null}
            {bestUsed.length > 0 ? (
              <p className="text-xs text-gray-500 mt-1" data-testid={`report-best-for-${report.id}`}>
                <span className="font-medium text-gray-600">Best used for:</span>{' '}
                {bestUsed.join(' · ')}
              </p>
            ) : null}
            {pres.ecosystemRole ? (
              <p className="text-xs text-gray-400 mt-2 italic">{pres.ecosystemRole}</p>
            ) : null}
            {pres.governanceNote ? (
              <p className="text-[11px] text-gray-400 mt-2 leading-relaxed" data-testid={`report-governance-${report.id}`}>
                {pres.governanceNote}
              </p>
            ) : null}
            {report.disclosure && report.disclosure !== pres.governanceNote ? (
              <p className="text-[11px] text-gray-400 mt-1">{report.disclosure}</p>
            ) : null}

            <div className="flex flex-wrap items-center gap-2 text-[11px] text-gray-400 mt-3 mb-3">
              <span>Formats:</span>
              {formats.map((f) => (
                <span key={f} className="px-1.5 py-0.5 bg-gray-100 rounded uppercase font-medium">
                  {f}
                </span>
              ))}
            </div>

            {formatHint && formats.includes(selectedFormat) ? (
              <p className="text-[11px] text-gray-500 mb-3">{formatHint}</p>
            ) : null}

            {specialtyAction ? (
              specialtyAction
            ) : (
              <Button
                onClick={() => onDownload(report.id, report.endpoint)}
                disabled={generating === report.id || !formats.includes(selectedFormat)}
                className="w-full"
                variant={pres.ecosystemGroup === 'evidentiary' ? 'outline' : 'default'}
                data-testid={`download-${report.id}-btn`}
              >
                {generating === report.id ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                    Generating…
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4 mr-2" />
                    Download {selectedFormat.toUpperCase()}
                  </>
                )}
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function ReportSpecialtyLinkCard({ report, icon, to, label }) {
  const pres = report.presentation || {};
  const tier = reportCardTierClass(pres.ecosystemGroup);

  return (
    <Card className={cn('transition-shadow hover:shadow-md', tier)} data-testid={`report-card-${report.id}`}>
      <CardContent className="p-5">
        <div className="flex items-start gap-3">
          {icon ? <div className="p-2.5 bg-gray-50 rounded-lg shrink-0">{icon}</div> : null}
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h3 className="font-semibold text-midnight-blue text-base">{report.name}</h3>
              {report.displayExportGrade ? (
                <span
                  className="text-[11px] uppercase tracking-wide text-gray-500 border border-gray-200 rounded px-1.5 py-0.5"
                  data-testid={`report-grade-${report.id}`}
                >
                  {report.displayExportGrade}
                </span>
              ) : null}
            </div>
            <p className="text-sm text-gray-700">{report.description}</p>
            {pres.governanceNote ? (
              <p className="text-[11px] text-gray-400 mt-2">{pres.governanceNote}</p>
            ) : null}
            <Button asChild className="w-full mt-4" variant="outline">
              <Link to={to} data-testid={`report-specialty-link-${report.id}`}>
                {label}
                <ArrowUpRight className="w-4 h-4 ml-2" />
              </Link>
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
