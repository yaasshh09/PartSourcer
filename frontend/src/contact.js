/**
 * Where to reach the project, in one place.
 *
 * The footer and the contact page both render these, and a handle that only
 * half the site knows about is how a stale link survives. Public on purpose:
 * this is a personal project and these are the ways in.
 */

const REPO = 'https://github.com/yaasshh09/PartSourcer'

export const CONTACT = {
  email: 'yashgupta2009yg@gmail.com',
  instagram: '@yaa.asshh',
  instagramUrl: 'https://instagram.com/yaa.asshh',
  github: 'yaasshh09',
  githubUrl: 'https://github.com/yaasshh09',
  repoUrl: REPO,
  issuesUrl: `${REPO}/issues`,
  licenseUrl: `${REPO}/blob/main/LICENSE`,
}

/**
 * A new issue that already says what the page showed, so a report only has
 * to add what the distributor says instead. Numbers go in as shown, since a
 * report about a rounded price must quote the rounding.
 */
export function reportHref({ mpn, distributor, sku, stock, price, asOf, page }) {
  const title = `Wrong data: ${mpn || 'part'} on ${distributor}${sku ? ` (${sku})` : ''}`
  const body = [
    `Page: ${page || ''}`,
    `Distributor: ${distributor}`,
    `SKU: ${sku || 'none'}`,
    `Stock shown: ${stock}`,
    `Price shown: ${price}`,
    `Read at: ${asOf || 'unknown'}`,
    '',
    'What the distributor shows instead:',
    '',
  ].join('\n')
  return `${REPO}/issues/new?${new URLSearchParams({ title, body })}`
}
