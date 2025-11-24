'use server';

import * as cheerio from 'cheerio';
import { prisma } from '@/lib/prisma';
import { revalidatePath } from 'next/cache';

/* ---------------- RELIANCE DIGITAL SCRAPER ---------------- */
async function getRelianceDigitalArticleId(url) {
  try {
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Mobile Safari/537.36',
      },
    });
    if (!res.ok) return null;

    const html = await res.text();
    const $ = cheerio.load(html);
    let id = null;

    $('li.specifications-list').each((_i, el) => {
      const label = $(el).find('span:first-child').text().trim();
      if (label === 'Item Code') {
        id = $(el).find('.specifications-list--right ul').text().trim();
        return false;
      }
    });

    if (!id) {
      const meta = $('meta[property="og:image"]').attr('content');
      const match = meta?.match(/-(\d{9})-i-1/);
      if (match) id = match[1];
    }

    return id;
  } catch {
    return null;
  }
}

/* ---------------- NEW: OPPO VARIANT FETCH (SERVER ACTION) ---------------- */
export async function fetchOppoVariantsServer(url) {
  try {
    const m = url.match(/\.P\.(P\d+)/i);
    if (!m) return [];
    const productCode = m[1];

    const payload = {
      productCode,
      userGroupName: "",
      storeViewCode: "in",
      configModule: 3,
      settleChannel: 3
    };

    const res = await fetch("https://opsg-gateway-in.oppo.com/v2/api/rest/mall/product/detail/fetch", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "client-version": "13.0.0.0",
        "platform": "web",
        "language": "en-IN",
        "User-Agent": "Mozilla/5.0",
      },
      body: JSON.stringify(payload),
      cache: "no-store"
    });

    const data = await res.json();
    const products = data?.data?.products || [];
    return products.map(p => ({
      sku: p.skuCode,
      name: p.name
    }));
  } catch {
    return [];
  }
}

/* ---------------- URL PARSER FOR ALL STORES ---------------- */
async function getProductDetails(url, partNumber) {
  try {
    const u = new URL(url);

    /* Vivo */
    if (u.hostname.includes('vivo.com') && !u.hostname.includes('iqoo.com')) {
      const parts = u.pathname.split('/').filter(Boolean);
      const pid = parts.pop();
      const name = `(Vivo) ${parts.pop()?.replace(/-/g, ' ') || 'Vivo Product'}`;
      return { name, productId: pid, storeType: 'vivo', partNumber: null };
    }

    /* iQOO */
    if (u.hostname.includes('iqoo.com')) {
      const parts = u.pathname.split('/').filter(Boolean);
      const pid = parts.pop();
      const name = `(iQOO) ${parts.pop()?.replace(/-/g, ' ') || 'iQOO Product'}`;
      return { name, productId: pid, storeType: 'iqoo', partNumber: null };
    }

    /* Reliance Digital */
    if (u.hostname.includes('reliancedigital.in')) {
      const internalId = await getRelianceDigitalArticleId(url);
      if (!internalId) throw new Error('Could not extract Reliance Item Code');

      const parts = u.pathname.split('/').filter(Boolean);
      const base = parts.at(-2) || 'RD Product';
      const name = `(R. Digital) ${base.replace(/-/g, ' ')}`;
      return { name, productId: internalId, storeType: 'reliance_digital', partNumber: parts.at(-1) };
    }

    /* Flipkart */
    if (u.hostname.includes('flipkart.com')) {
      const pid = u.searchParams.get('pid');
      if (!pid) throw new Error("Flipkart 'pid' missing");
      const nm = `(Flipkart) ${u.pathname.split('/')[1].replace(/-/g, ' ')}`;
      return { name: nm, productId: pid, storeType: 'flipkart', partNumber: null };
    }

    /* Amazon */
    if (u.hostname.includes('amazon.in')) {
      const parts = u.pathname.split('/');
      const dp = parts.indexOf('dp');
      if (dp === -1 || !parts[dp + 1]) throw new Error('Invalid Amazon DP URL');
      const asin = parts[dp + 1];
      const nm = `(Amazon) ${(parts[dp - 1] || 'Amazon Product').replace(/-/g, ' ')}`;
      return { name: nm, productId: asin, storeType: 'amazon', partNumber: null };
    }

    /* Apple */
    if (u.hostname.includes('apple.com')) {
      if (!partNumber) throw new Error('Apple requires Part Number');
      const title = u.pathname.split('/')[3] || 'Apple Product';
      const nm = `(Apple) ${title.replace(/-/g, ' ')}`;
      return { name: nm, productId: partNumber, storeType: 'apple', partNumber };
    }

    /* Croma */
    if (u.hostname.includes('croma.com')) {
      const parts = u.pathname.split('/');
      const pid = parts.pop();
      if (!/^\d+$/.test(pid)) throw new Error('Invalid Croma PID');
      return { name: `(Croma) ${parts[1].replace(/-/g, ' ')}`, productId: pid, storeType: 'croma', partNumber: null };
    }

    /* -------- 🟢 OPPO — FINAL STEP (SKU already selected in UI) -------- */
    if (u.hostname.includes('oppo.com')) {
      if (!partNumber) throw new Error('Please select OPPO variant first');
      return {
        name: `(OPPO) Product`,
        productId: partNumber, // SKU
        storeType: 'oppo',
        partNumber
      };
    }

    throw new Error('Unsupported store URL');
  } catch (err) {
    return { error: err.message };
  }
}

/* ---------------- ADD PRODUCT ---------------- */
export async function addProduct(formData) {
  const url = formData.get('url');
  const partNumber = formData.get('partNumber') || null;
  const affiliateLink = formData.get('affiliateLink') || null;

  const details = await getProductDetails(url, partNumber);
  if (details.error) return { error: details.error };

  try {
    const saved = await prisma.product.create({
      data: {
        name: details.name,
        url,
        productId: details.productId,
        storeType: details.storeType,
        partNumber: details.partNumber,
        affiliateLink,
      },
    });

    revalidatePath('/');
    return { success: `Added ${saved.name}`, product: saved };
  } catch {
    return { error: 'Failed to add product (duplicate?)' };
  }
}

/* ---------------- DELETE PRODUCT ---------------- */
export async function deleteProduct(id) {
  if (!id) return;
  try {
    await prisma.product.delete({ where: { id } });
    revalidatePath('/');
  } catch {}
}
