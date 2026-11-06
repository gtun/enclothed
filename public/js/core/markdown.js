/* Turns the markdown in AI answers into safe HTML. Everything is escaped first, so only the tags
   written here can appear, whatever text an answer contains. Handles paragraphs, headings, lists,
   tables, code, bold and italics, plus [[garment:ID]] tokens, which become garment photos. */
"use strict";

const GARMENT_TOKEN = /\[\[\s*garment\s*:\s*(\d+)\s*\]\]/gi;
const GARMENTS_ONLY_LINE = /^(\s*\[\[\s*garment\s*:\s*\d+\s*\]\]\s*)+$/i;
const LIST_ITEM = /^\s*(?:[-*+]|\d+[.)])\s+(.*)$/;
const ORDERED_ITEM = /^\s*\d+[.)]\s/;
const HEADING = /^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$/;
const RULE = /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/;
const FENCE = /^\s*```/;
const QUOTE = /^\s*>\s?/;

function mdInline(text, garmentRef){
  return String(text).split(/(`[^`\n]+`)/).map(part => {
    if (/^`[^`\n]+`$/.test(part)) return `<code>${esc(part.slice(1, -1))}</code>`;
    return esc(part)
      .replace(/\*\*(?=\S)(.+?)(?<=\S)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*\w])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![*\w])/g, "$1<em>$2</em>")
      .replace(GARMENT_TOKEN, (_, id) => garmentRef(id));
  }).join("");
}
const tableCells = line => line.trim().replace(/^\|/, "").replace(/(?<!\\)\|$/, "").split(/(?<!\\)\|/).map(cell => cell.trim().replace(/\\\|/g, "|"));
const isTableDivider = line => line.includes("-") && /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/.test(line);
const startsTable = (lines, i) => lines[i].includes("|") && i + 1 < lines.length && isTableDivider(lines[i + 1]);
const cellAlign = cell => /^:?-+:$/.test(cell) ? (cell.startsWith(":") ? "center" : "right") : "";

function mdTable(head, divider, rows, inline){
  const aligns = tableCells(divider).map(cellAlign);
  const cell = (tag, text, i) => `<${tag}${aligns[i] ? ` style="text-align:${aligns[i]}"` : ""}>${inline(text)}</${tag}>`;
  const headRow = tableCells(head).map((text, i) => cell("th", text, i)).join("");
  const body = rows.map(row => `<tr>${tableCells(row).map((text, i) => cell("td", text, i)).join("")}</tr>`).join("");
  return `<div class="itable"><table><thead><tr>${headRow}</tr></thead><tbody>${body}</tbody></table></div>`;
}
/* garmentRef(id) is one photo inside a line of text; garmentRow(ids) is a line of nothing but photos. */
function renderMarkdown(text, garmentRef, garmentRow){
  const inline = t => mdInline(t, garmentRef);
  const lines = String(text).replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  const startsBlock = i => !lines[i].trim() || FENCE.test(lines[i]) || HEADING.test(lines[i]) || RULE.test(lines[i]) || LIST_ITEM.test(lines[i])
    || QUOTE.test(lines[i]) || GARMENTS_ONLY_LINE.test(lines[i]) || startsTable(lines, i);
  let i = 0;
  while (i < lines.length){
    const line = lines[i];
    if (!line.trim()){ i++; continue; }
    if (FENCE.test(line)){
      const code = [];
      for (i++; i < lines.length && !FENCE.test(lines[i]); i++) code.push(lines[i]);
      i++;
      blocks.push(`<pre>${esc(code.join("\n"))}</pre>`);
    } else if (GARMENTS_ONLY_LINE.test(line)){
      blocks.push(garmentRow([...line.matchAll(GARMENT_TOKEN)].map(m => m[1])));
      i++;
    } else if (startsTable(lines, i)){
      const head = line, divider = lines[i + 1], rows = [];
      for (i += 2; i < lines.length && lines[i].trim() && lines[i].includes("|"); i++) rows.push(lines[i]);
      blocks.push(mdTable(head, divider, rows, inline));
    } else if (HEADING.test(line)){
      blocks.push(`<h4>${inline(line.match(HEADING)[1])}</h4>`);
      i++;
    } else if (RULE.test(line)){
      blocks.push("<hr>");
      i++;
    } else if (LIST_ITEM.test(line)){
      const tag = ORDERED_ITEM.test(line) ? "ol" : "ul", items = [];
      for (; i < lines.length && LIST_ITEM.test(lines[i]); i++) items.push(`<li>${inline(lines[i].match(LIST_ITEM)[1])}</li>`);
      blocks.push(`<${tag}>${items.join("")}</${tag}>`);
    } else if (QUOTE.test(line)){
      const quoted = [];
      for (; i < lines.length && QUOTE.test(lines[i]); i++) quoted.push(inline(lines[i].replace(QUOTE, "")));
      blocks.push(`<blockquote>${quoted.join("<br>")}</blockquote>`);
    } else {
      const para = [inline(line)];
      for (i++; i < lines.length && !startsBlock(i); i++) para.push(inline(lines[i]));
      blocks.push(`<p>${para.join("<br>")}</p>`);
    }
  }
  return blocks.join("");
}
