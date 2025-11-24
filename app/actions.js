'use server';

import * as cheerio from 'cheerio';
import { prisma } from '@/lib/prisma';
import { revalidatePath } from 'next/cache';

/**
 * Reliance Digital scraper — unchanged
 */
async function getRelianceDigitalArticleId(url) {
    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142 Mobile Safari/537.36',
            },
        });
        if (!response.ok) return null;
        const html = await response.text();
        const $ = cheerio.load(html);
        let articleId = null;

        $('li.specifications-list').each((i, el) => {
            const label = $(el).find('span:first-child').text().trim();
            if (label === 'Item Code') {
                articleId = $(el).find('.specifications-list--right ul').text().trim();
                return false;
            }
        });

        if (!articleId) {
            const meta = $('meta[property="og:image"]').attr('content');
            const match = meta?.match(/-(\d{9})-i-1/);
            if (match) articleId = match[1];
        }

        return articleId;
    } catch {
        return null;
    }
}

/**
 * MASTER URL PARSER + ID/NAME BUILDER
 */
async function getProductDetails(url, partNumber) {
    try {
        const parsedUrl = new URL(url);

        /** -------------------- VIVO -------------------- */
        if (parsedUrl.hostname.includes('vivo.com') && !parsedUrl.hostname.includes('iqoo.com')) {
            const parts = parsedUrl.pathname.split('/').filter(Boolean);
            const pid = parts.pop();
            const base = parts.pop() || 'Vivo Product';
            const name = '(Vivo) ' + base.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase()).slice(0, 50);
            return { name, productId: pid, storeType: 'vivo', partNumber: null };
        }

        /** -------------------- IQOO -------------------- */
        if (parsedUrl.hostname.includes('iqoo.com')) {
            const parts = parsedUrl.pathname.split('/').filter(Boolean);
            const pid = parts.pop();
            const base = parts.pop() || 'iQOO Product';
            const name = '(iQOO) ' + base.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase()).slice(0, 50);
            return { name, productId: pid, storeType: 'iqoo', partNumber: null };
        }

        /** ---------------- RELIANCE DIGITAL ---------------- */
        if (parsedUrl.hostname.includes('reliancedigital.in')) {
            const internalId = await getRelianceDigitalArticleId(url);
            if (!internalId) throw new Error("Unable to scrape Reliance Digital Item Code");
            const slug = parsedUrl.pathname.split('/').filter(Boolean).pop();
            const base = parsedUrl.pathname.split('/').filter(Boolean).slice(-2, -1)[0];
            const name = `(R. Digital) ${base.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}`;
            return { name, productId: internalId, storeType: 'reliance_digital', partNumber: slug };
        }

        /** -------------------- FLIPKART -------------------- */
        if (parsedUrl.hostname.includes('flipkart.com')) {
            const pid = parsedUrl.searchParams.get('pid');
            if (!pid) throw new Error("Flipkart PID missing in URL");
            const name = `(Flipkart) ${parsedUrl.pathname.split('/')[1].replace(/-/g, ' ')}`;
            return { name, productId: pid, storeType: 'flipkart', partNumber: null };
        }

        /** -------------------- AMAZON -------------------- */
        if (parsedUrl.hostname.includes('amazon.in')) {
            const parts = parsedUrl.pathname.split('/');
            const dpIndex = parts.indexOf('dp');
            if (dpIndex === -1 || !parts[dpIndex + 1]) throw new Error("Invalid Amazon /dp/ASIN URL");
            const asin = parts[dpIndex + 1];
            const name = `(Amazon) ${(parts[dpIndex - 1] || 'Amazon Product').replace(/-/g, ' ')}`;
            return { name, productId: asin, storeType: 'amazon', partNumber: null };
        }

        /** -------------------- APPLE -------------------- */
        if (parsedUrl.hostname.includes('apple.com')) {
            if (!partNumber) throw new Error("Apple requires Part Number");
            const title = parsedUrl.pathname.split('/')[3] || 'Apple Product';
            const name = `(Apple) ${title.replace(/-/g, ' ')}`;
            return { name, productId: partNumber, storeType: 'apple', partNumber };
        }

        /** -------------------- CROMA -------------------- */
        if (parsedUrl.hostname.includes('croma.com')) {
            const parts = parsedUrl.pathname.split('/');
            const pid = parts.pop();
            if (!/^\d+$/.test(pid)) throw new Error("Invalid Croma PID");
            const name = `(Croma) ${parts[1].replace(/-/g, ' ')}`;
            return { name, productId: pid, storeType: 'croma', partNumber: null };
        }

        /** ----------------------------------------------------------- */
        /** 🟢 NEW — OPPO — SKU logic (variant already selected in UI)  */
        /** ----------------------------------------------------------- */
        if (parsedUrl.hostname.includes('oppo.com')) {
            // UI already supplied the SKU via 'partNumber' / productId
            if (!partNumber) throw new Error("Please select OPPO variant first");
            return {
                name: `(OPPO) Product`, // name replaced with real variant name after saving
                productId: partNumber, // SKU CODE
                storeType: 'oppo',
                partNumber
            };
        }

        /** ---------------- UNSUPPORTED ---------------- */
        throw new Error("Only Croma, Apple, Amazon, Flipkart, Vivo, iQOO, Reliance Digital, and OPPO URLs are supported.");
    } catch (err) {
        return { error: err.message };
    }
}

/**
 * Add product to database
 */
export async function addProduct(formData) {
    const url = formData.get('url');
    const partNumber = formData.get('partNumber') || null;
    const affiliateLink = formData.get('affiliateLink') || null;

    if (!url) return { error: 'URL is required.' };

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
                affiliateLink
            }
        });

        revalidatePath('/');

        return { success: `Added ${saved.name}`, product: saved };
    } catch (err) {
        return { error: "Failed to add product — possible duplicate?" };
    }
}

/**
 * Delete Product
 */
export async function deleteProduct(id) {
    if (!id) return;
    try {
        await prisma.product.delete({ where: { id } });
        revalidatePath('/');
    } catch {}
}
