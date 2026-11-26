/**
 * Formats a monetary amount into Indian Rupee format (e.g. ₹1,50,000.00).
 */
export function formatINR(amount: number | string | undefined | null): string {
  if (amount === undefined || amount === null) {
    return '₹0.00';
  }
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) {
    return '₹0.00';
  }

  const isNegative = num < 0;
  const absNum = Math.abs(num);

  const formatted = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(absNum);

  return isNegative ? `-${formatted}` : formatted;
}

/**
 * Formats an ISO date string (YYYY-MM-DD or ISO timestamp) into DD/MM/YYYY.
 */
export function formatDate(dateStr: string | undefined | null): string {
  if (!dateStr) return '';
  try {
    const parts = dateStr.split('T')[0].split('-');
    if (parts.length === 3) {
      return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }
    const d = new Date(dateStr);
    if (!isNaN(d.getTime())) {
      const day = String(d.getDate()).padStart(2, '0');
      const month = String(d.getMonth() + 1).padStart(2, '0');
      const year = d.getFullYear();
      return `${day}/${month}/${year}`;
    }
    return dateStr;
  } catch {
    return dateStr;
  }
}
