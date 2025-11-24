'use client';

import { useRef, useState, useEffect } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { fetchOppoVariantsServer } from '@/app/actions';

/* Store detection helper */
function getStoreDetails(url) {
  const u = url.toLowerCase();
  if (u.includes('apple.com')) return { storeType: 'unicorn', showPartNumber: true, extracted: null };
  if (u.includes('flipkart.com')) return { storeType: 'unknown', showPartNumber: true, extracted: new URL(url).searchParams.get('pid') };
  if (u.includes('amazon.in')) return { storeType: 'unknown', showPartNumber: true, extracted: url.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/i)?.[1] || null };
  if (u.includes('croma.com')) return { storeType: 'unknown', showPartNumber: true, extracted: url.split('/').filter(Boolean).pop() };
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
    if (extracted) setProductId(extracted);
    else if (!url || !showPartNumber) setProductId('');
  }, [url, extracted, showPartNumber]);

  useEffect(() => {
    async function load() {
      if (!url.toLowerCase().includes('oppo.com')) {
        setVariants([]);
        setSelectedVariant('');
        return;
      }
      const v = await fetchOppoVariantsServer(url);
      setVariants(v);
    }
    load();
  }, [url]);

  async function formAction(formData) {
    formData.append('storeType', storeType);

    if (showPartNumber && productId) {
      formData.append('partNumber', productId);
      formData.append('productId', productId);
    }

    if (storeType === 'oppo') {
      if (!selectedVariant) return toast.error('Select an OPPO variant first');
      formData.append('productId', selectedVariant);
      formData.append('partNumber', selectedVariant);
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

  return (
    <form ref={formRef} action={formAction} className="flex flex-col w-full space-y-3">
      <div className="flex w-full items-center space-x-2">
        <Input type="text" name="url" placeholder="Paste product URL" required value={url} onChange={e => setUrl(e.target.value)} />
        <Button type="submit">Add Product</Button>
      </div>

      {storeType === 'oppo' && variants.length > 0 && (
        <select className="border p-2 rounded" value={selectedVariant} onChange={e => setSelectedVariant(e.target.value)}>
          <option value="">Select OPPO Variant (SKU)</option>
          {variants.map(v => (
            <option value={v.sku} key={v.sku}>{v.name}</option>
          ))}
        </select>
      )}

      {showPartNumber && (
        <Input
          type="text"
          name="partNumber"
          value={productId}
          placeholder="Product ID"
          required
          onChange={e => setProductId(e.target.value)}
        />
      )}

      <Input type="text" name="affiliateLink" placeholder="Affiliate Link (optional)" />
    </form>
  );
}
