'use client';

import { useRef, useState, useEffect } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

/**
 * URL-based extraction helpers
 */
function extractFlipkartProductId(url) {
  try {
    return new URL(url).searchParams.get('pid');
  } catch {
    return null;
  }
}

function extractAmazonAsin(url) {
  try {
    const match = new URL(url).pathname.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/i);
    return match ? match[1] : null;
  } catch {
    return null;
  }
}

function extractCromaProductId(url) {
  try {
    const last = new URL(url).pathname.split('/').filter(Boolean).pop();
    return /^\d+$/.test(last) ? last : null;
  } catch {
    return null;
  }
}

function extractApplePartNumber(url) {
  let match = url.match(/\/product\/([^/?]+)/i);
  if (match && match[1]) return match[1];
  match = url.match(/([A-Z0-9]{5,}[A-Z0-9]\/[A-Z0-9])/i);
  return match && match[1] && match[1].length > 7 ? match[1] : null;
}

/**
 * Store type detection
 */
function getStoreDetails(url) {
  const l = url.toLowerCase();
  if (l.includes('apple.com')) return { storeType: 'unicorn', showPartNumber: true, extractedPartNumber: extractApplePartNumber(url) };
  if (l.includes('flipkart.com')) return { storeType: 'unknown', showPartNumber: true, extractedPartNumber: extractFlipkartProductId(url) };
  if (l.includes('amazon.in')) return { storeType: 'unknown', showPartNumber: true, extractedPartNumber: extractAmazonAsin(url) };
  if (l.includes('croma.com')) return { storeType: 'unknown', showPartNumber: true, extractedPartNumber: extractCromaProductId(url) };

  if (l.includes('reliancedigital.in')) return { storeType: 'reliance_digital', showPartNumber: false, extractedPartNumber: null };
  if (l.includes('iqoo.com')) return { storeType: 'iqoo', showPartNumber: false, extractedPartNumber: null };
  if (l.includes('vivo.com')) return { storeType: 'vivo', showPartNumber: false, extractedPartNumber: null };

  // 🟢 NEW — OPPO
  if (l.includes('oppo.com')) return { storeType: 'oppo', showPartNumber: false, extractedPartNumber: null };

  return { storeType: 'unknown', showPartNumber: false, extractedPartNumber: null };
}

export function AddProductForm({ addProductAction }) {
  const formRef = useRef(null);
  const [url, setUrl] = useState('');
  const [productId, setProductId] = useState('');
  const { storeType, showPartNumber, extractedPartNumber } = getStoreDetails(url);

  // 🟢 NEW — OPPO SKU state
  const [variants, setVariants] = useState([]);
  const [selectedVariant, setSelectedVariant] = useState("");

  // Existing auto-population logic
  useEffect(() => {
    if (extractedPartNumber) {
      setProductId(extractedPartNumber);
      return;
    }
    if (!url || !showPartNumber) {
      setProductId('');
      return;
    }
  }, [url, extractedPartNumber, showPartNumber]);

  // 🟢 NEW — Fetch OPPO variants when URL enters
  useEffect(() => {
    async function fetchOppo() {
      if (!url.toLowerCase().includes("oppo.com")) {
        setVariants([]);
        setSelectedVariant("");
        return;
      }

      const m = url.match(/\.P\.(P\d+)/i);
      if (!m) return;
      const productCode = m[1];

      try {
        const res = await fetch("https://opsg-gateway-in.oppo.com/v2/api/rest/mall/product/detail/fetch", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "client-version": "13.0.0.0",
            "platform": "web",
            "language": "en-IN",
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://www.oppo.com",
            "Referer": url
          },
          body: JSON.stringify({
            productCode,
            userGroupName: "",
            storeViewCode: "in",
            configModule: 3,
            settleChannel: 3
          })
        });

        const data = await res.json();
        const list = data?.data?.products || [];
        setVariants(list.map(p => ({ sku: p.skuCode, name: p.name })));
      } catch {
        setVariants([]);
      }
    }
    fetchOppo();
  }, [url]);

  async function formAction(formData) {
    formData.append('storeType', storeType);

    // For Apple / Flipkart / Amazon / Croma
    if (showPartNumber && productId) {
      formData.append('partNumber', productId);
      formData.append('productId', productId);
    }

    // 🟢 NEW — OPPO sends SKU instead
    if (storeType === "oppo") {
      if (!selectedVariant) return toast.error("⚠ Select a variant first");
      formData.append("productId", selectedVariant);
      formData.append("partNumber", selectedVariant);
    }

    const result = await addProductAction(formData);
    if (result?.error) return toast.error(result.error);

    toast.success("Product added to tracker!");
    formRef.current?.reset();
    setUrl('');
    setProductId('');
    setVariants([]);
    setSelectedVariant('');
  }

  const placeholderText =
    storeType === 'unknown'
      ? "Paste Product URL (Flipkart, Amazon, Croma, OPPO, etc)"
      : `Paste ${storeType.replace('_', ' ').toUpperCase()} URL`;

  return (
    <form ref={formRef} action={formAction} className="flex flex-col w-full space-y-3">
      {/* URL Input */}
      <div className="flex w-full items-center space-x-2">
        <Input
          type="text"
          name="url"
          placeholder={placeholderText}
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <Button type="submit">Add Product</Button>
      </div>

      {/* SKU Dropdown for OPPO */}
      {storeType === "oppo" && variants.length > 0 && (
        <select
          className="border p-2 rounded"
          value={selectedVariant}
          onChange={(e) => setSelectedVariant(e.target.value)}
        >
          <option value="">Select OPPO Variant (SKU)</option>
          {variants.map(v => (
            <option key={v.sku} value={v.sku}>{v.name}</option>
          ))}
        </select>
      )}

      {/* Product ID textbox (only for Apple / Flipkart / Amazon / Croma) */}
      {showPartNumber && (
        <Input
          type="text"
          name="partNumber"
          value={productId}
          onChange={(e) => setProductId(e.target.value)}
          placeholder="Product ID (auto detected)"
          required
        />
      )}

      {/* Affiliate link input */}
      <Input
        type="text"
        name="affiliateLink"
        placeholder="Your Affiliate Link (Optional)"
      />
    </form>
  );
}
