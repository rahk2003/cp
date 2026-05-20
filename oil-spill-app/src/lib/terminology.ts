/** توحيد المصطلحات العربية في واجهة المستخدم وردود الوكيل. */
export function normalizeArabicUiTerms(text: string): string {
  if (!text) return text;
  let out = text;
  out = out.replace(/المساعد الذكي/g, "الوكيل الذكي");
  out = out.replace(/مساعدك الذكي/g, "وكيلك الذكي");
  out = out.replace(/المساعد/g, "الوكيل");
  out = out.replace(/من الشعاب(?! المرجانية)/g, "من الشعاب المرجانية");
  out = out.replace(/والشعاب(?! المرجانية)/g, "والشعاب المرجانية");
  out = out.replace(/قرب الشعاب(?! المرجانية)/g, "قرب الشعاب المرجانية");
  out = out.replace(/إلى الشعاب(?! المرجانية)/g, "إلى الشعاب المرجانية");
  out = out.replace(/عن الشعاب(?! المرجانية)/g, "عن الشعاب المرجانية");
  out = out.replace(/\bالشعب\b/g, "الشعاب المرجانية");
  out = out.replace(/\bالشعاب\b(?! المرجانية)/g, "الشعاب المرجانية");
  out = out.replace(/(?<!جيو )مكانية/g, "جيو المكانية");
  out = out.replace(/(?<!جيو )مكاني(?!ة)/g, "جيو مكاني");
  out = out.replace(/القناع المتوقّع/g, "منطقة التسرب المكتشفة");
  out = out.replace(/القناع المتوقع/g, "منطقة التسرب المكتشفة");
  out = out.replace(/قناع متوقّع/g, "منطقة التسرب المكتشفة");
  out = out.replace(/قناع متوقع/g, "منطقة التسرب المكتشفة");
  out = out.replace(/التراكب/g, "التداخل");
  out = out.replace(/فضائية/g, "أقمار صناعية");
  out = out.replace(/فضائي/g, "أقمار صناعية");
  out = out.replace(/زيت/g, "نفط");
  out = out.replace(/المنصة/g, "النظام");
  out = out.replace(/منصة/g, "نظام");
  out = out.replace(/السمات/g, "الخصائص");
  out = out.replace(/السمة/g, "الخاصية");
  out = out.replace(/سمات/g, "خصائص");
  out = out.replace(/سمة/g, "خاصية");
  out = out.replace(/لا يوجد تسرب/g, "لا يوجد تسرب");
  out = out.replace(/حرج/g, "عالي");
  out = out.replace(/Critical/gi, "High");
  return out;
}
