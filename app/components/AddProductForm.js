'use client';

import { useRef, useState, useEffect } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { fetchOppoVariantsServer } from '@/app/actions';

/* Store detection helper */
function getStoreDetails(url) {
  const u = url.toLowerCase();
  // --- ADDED JIOMART ---
  if (u.includes('jiomart.com')) return { storeType: 'jiomart', showPartNumber: false, extracted: null };
  // --------------------

  if (u.includes('apple.com')) return { storeType: 'unicorn', showPartNumber: true, extracted: null };
  if (u.includes('flipkart.com')) return { storeType: 'flipkart', showPartNumber: true, extracted: new URL(url).searchParams.get('pid') };
  if (u.includes('amazon.in')) {
    const match = url.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/i);
    return { storeType: 'amazon', showPartNumber: true, extracted: match ? match[1] : null };
  }
  if (u.includes('croma.com')) {
    const parts = url.split('/').filter(Boolean);
    const extracted = parts.pop();
    return { storeType: 'croma', showPartNumber: true, extracted: /^\d+$/.test(extracted) ? extracted : null };
  }
  if (u.includes('reliancedigital.in')) return { storeType: 'reliance_digital', showPartNumber: false, extracted: null };
  if (u.includes('iqoo.com')) return { storeType: 'iqoo', showPartNumber: false, extracted: null };
  if (u.includes('vivo.com')) return { storeType: 'vivo', showPartNumber: false, extracted: null };
  if (u.includes('oppo.com')) return { storeType: 'oppo', showPartNumber: false, extracted: null };
  
  return { storeType: 'unknown', showPartNumber: false, extracted: null };
}

export function AddProductForm({ addProductAction }) {
  const formRef = useRef(null);
  const [url, setUrl] = useState('');
  const [productId, setProductId] = useState('');
  const { storeType, showPartNumber, extracted } = getStoreDetails(url);

  /* OPPO state */
  const [variants, setVariants] = useState([]);
  const [selectedVariant, setSelectedVariant] = useState('');

  useEffect(() => {
    // If we have an extracted ID and the store needs manual input (like Flipkart/Amazon), use it.
    if (extracted && showPartNumber) setProductId(extracted);
    // Otherwise, clear the manual ID unless it's a store that doesn't need manual input (Jiomart, Vivo, iQOO, RD, OPPO)
    else if (!url || !showPartNumber) setProductId('');
  }, [url, extracted, showPartNumber]);

  useEffect(() => {
    async function load() {
      if (storeType !== 'oppo') {
        setVariants([]);
        setSelectedVariant('');
        return;
      }
      // Extract the product code from the full URL for OPPO
      const v = await fetchOppoVariantsServer(url);
      setVariants(v);
    }
    load();
  }, [url, storeType]);

  async function formAction(formData) {
    formData.append('storeType', storeType);

    // This handles Flipkart, Amazon, Croma, Apple
    if (showPartNumber && productId) {
      formData.append('partNumber', productId);
      formData.append('productId', productId);
    } 
    // This handles stores that don't require manual input (Jiomart, Vivo, iQOO, RD)
    else if (!showPartNumber && storeType !== 'oppo' && url) {
        // We do not append anything here. getProductDetails in actions.js
        // will handle extraction for these stores (Jiomart, Vivo, iQOO, RD)
    }
    // This handles the special case of OPPO variant selection
    else if (storeType === 'oppo') {
      if (!selectedVariant) return toast.error('Select an OPPO variant first');
      formData.append('productId', selectedVariant);
      formData.append('partNumber', selectedVariant); // partNumber will be SKU for consistency
    } else {
        return toast.error('Please enter a valid URL for a supported store.');
    }

    const res = await addProductAction(formData);
    if (res.error) return toast.error(res.error);

    toast.success('Product added!');
    formRef.current?.reset();
    setUrl('');
    setProductId('');
    setVariants([]);
    setSelectedVariant('');
  }

  const isOppoSelected = storeType === 'oppo';

  return (
    <form ref={formRef} action={formAction} className="flex flex-col w-full space-y-3">
      <div className="flex w-full items-center space-x-2">
        <Input type="url" name="url" placeholder="Paste product URL (Jiomart, Flipkart, Amazon, etc.)" required value={url} onChange={e => setUrl(e.target.value)} />
        <Button type="submit">Add Product</Button>
      </div>

      {isOppoSelected && variants.length > 0 && (
        <select className="border p-2 rounded" value={selectedVariant} onChange={e => setSelectedVariant(e.target.value)}>
          <option value="">Select OPPO Variant (SKU)</option>
          {variants.map(v => (
            <option value={v.sku} key={v.sku}>{v.name}</option>
          ))}
        </select>
      )}

      {showPartNumber && !isOppoSelected && (
        <Input
          type="text"
          name="partNumber"
          value={productId}
          placeholder="Product ID (e.g., ASIN/PID/Part# for Amazon/Flipkart/Apple)"
          required
          onChange={e => setProductId(e.target.value)}
        />
      )}

      <Input type="url" name="affiliateLink" placeholder="Affiliate Link (optional)" />
    </form>
  );
}
