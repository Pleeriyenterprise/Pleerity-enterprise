import React from 'react';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { formatMinorUnits } from '../../utils/rentMoney';

export function PropertyExpensesPanel({ expenses, expenseSummary, onAdd }) {
  return (
    <div data-testid="rent-expenses-panel">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold text-midnight-blue">Property expenses</h2>
        <Button size="sm" onClick={onAdd}>Add expense</Button>
      </div>
      {expenseSummary?.by_category?.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
          {expenseSummary.by_category.slice(0, 4).map((c) => (
            <Card key={c.category}>
              <CardContent className="p-3">
                <p className="text-xs text-gray-500">{c.category.replace(/_/g, ' ')}</p>
                <p className="font-semibold">{formatMinorUnits(c.total_minor)}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      {expenses.length === 0 ? (
        <Card data-testid="rent-expenses-empty">
          <CardContent className="py-8 text-center text-gray-500">No expenses recorded yet.</CardContent>
        </Card>
      ) : (
        <ul className="space-y-2">
          {expenses.map((ex) => (
            <li key={ex.expense_id} className="rounded-lg border p-3 flex justify-between items-start">
              <div>
                <p className="font-medium text-midnight-blue">{formatMinorUnits(ex.amount_minor, ex.currency)}</p>
                <p className="text-sm text-gray-600">{ex.category?.replace(/_/g, ' ')} · {ex.expense_date}</p>
                {ex.vendor_name && <p className="text-xs text-gray-500">{ex.vendor_name}</p>}
              </div>
              {ex.compliance_related && (
                <span className="text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded">Compliance</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
