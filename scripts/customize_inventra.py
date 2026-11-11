from pathlib import Path
import re

root = Path("inventra/app/src/main/java/com/inventra/app")

repo = root / "data/repository/InventraRepository.kt"
s = repo.read_text()
s = s.replace("import com.inventra.app.data.local.dao.CategoryDao", "import androidx.room.withTransaction\nimport com.inventra.app.data.local.InventraDatabase\nimport com.inventra.app.data.local.dao.CategoryDao")
s = s.replace("    private val saleDao: SaleDao\n)", "    private val saleDao: SaleDao,\n    private val database: InventraDatabase\n)")
a = s.index("    suspend fun addStockPurchase(purchase: StockPurchaseEntity) {")
b = s.index("\n    fun computeNewAvgCost", a)
s = s[:a] + """    suspend fun addStockPurchase(purchase: StockPurchaseEntity): Result<Unit> {
        if (!purchase.quantity.isFinite() || purchase.quantity <= 0.0)
            return Result.failure(IllegalArgumentException("الكمية يجب أن تكون أكبر من صفر"))
        if (!purchase.costPerUnit.isFinite() || purchase.costPerUnit < 0.0)
            return Result.failure(IllegalArgumentException("سعر التكلفة غير صالح"))
        return database.withTransaction {
            val product = productDao.getProductById(purchase.productId)
                ?: return@withTransaction Result.failure(IllegalArgumentException("المادة غير موجودة"))
            val existingValue = product.currentStockQty * product.currentAvgCost
            val newQty = product.currentStockQty + purchase.quantity
            val newAvgCost = (existingValue + purchase.quantity * purchase.costPerUnit) / newQty
            productDao.updateStockStats(purchase.productId, newQty, newAvgCost)
            stockPurchaseDao.insertPurchase(purchase)
            Result.success(Unit)
        }
    }
""" + s[b:]
a = s.index("    suspend fun addSale(")
b = s.index("\n    suspend fun deleteSale", a)
s = s[:a] + """    suspend fun addSale(
        productId: String,
        quantity: Double,
        sellingPricePerUnit: Double,
        date: Long,
        notes: String
    ): Result<Unit> {
        if (!quantity.isFinite() || quantity <= 0.0)
            return Result.failure(IllegalArgumentException("الكمية يجب أن تكون أكبر من صفر"))
        if (!sellingPricePerUnit.isFinite() || sellingPricePerUnit < 0.0)
            return Result.failure(IllegalArgumentException("سعر البيع غير صالح"))
        return database.withTransaction {
            val product = productDao.getProductById(productId)
                ?: return@withTransaction Result.failure(IllegalArgumentException("المادة غير موجودة"))
            if (product.currentStockQty < quantity)
                return@withTransaction Result.failure(IllegalArgumentException("الكمية المتوفرة غير كافية: ${product.currentStockQty}"))
            val totalRevenue = quantity * sellingPricePerUnit
            val avgCost = product.currentAvgCost
            val totalCost = quantity * avgCost
            val profit = totalRevenue - totalCost
            saleDao.insertSale(
                SaleEntity(
                    productId = productId,
                    quantity = quantity,
                    sellingPricePerUnit = sellingPricePerUnit,
                    totalRevenue = totalRevenue,
                    avgCostAtSale = avgCost,
                    totalCost = totalCost,
                    profit = profit,
                    date = date,
                    notes = notes
                )
            )
            productDao.updateStockStats(productId, product.currentStockQty - quantity, avgCost)
            Result.success(Unit)
        }
    }
""" + s[b:]
repo.write_text(s)

vm = root / "presentation/stock/StockViewModel.kt"
s = vm.read_text()
s = s.replace('''            repository.addStockPurchase(
                StockPurchaseEntity(
                    productId = productId, quantity = quantity, costPerUnit = costPerUnit,
                    totalCost = quantity * costPerUnit, date = date, supplier = supplier, notes = notes
                )
            )
            _result.value = StockInResult.Success''', '''            if (!costPerUnit.isFinite() || costPerUnit < 0) {
                _result.value = StockInResult.Error("سعر التكلفة غير صالح")
                return@launch
            }
            val outcome = repository.addStockPurchase(
                StockPurchaseEntity(
                    productId = productId, quantity = quantity, costPerUnit = costPerUnit,
                    totalCost = quantity * costPerUnit, date = date, supplier = supplier, notes = notes
                )
            )
            _result.value = outcome.fold(
                onSuccess = { StockInResult.Success },
                onFailure = { StockInResult.Error(it.message ?: "حدث خطأ غير معروف") }
            )''')
vm.write_text(s)

sales = root / "presentation/sales/SalesViewModel.kt"
s = sales.read_text()
s = s.replace('''            if (quantity <= 0) { _result.value = AddSaleResult.Error("Quantity must be > 0"); return@launch }
            if (sellingPrice < 0) { _result.value = AddSaleResult.Error("Selling price cannot be negative"); return@launch }''', '''            if (!quantity.isFinite() || quantity <= 0) { _result.value = AddSaleResult.Error("الكمية يجب أن تكون أكبر من صفر"); return@launch }
            if (!sellingPrice.isFinite() || sellingPrice < 0) { _result.value = AddSaleResult.Error("سعر البيع غير صالح"); return@launch }''')
sales.write_text(s)

strings = Path("inventra/app/src/main/res/values/strings.xml")
if strings.exists():
    t = strings.read_text()
    t = re.sub(r'(<string name="app_name">).*?(</string>)', r'\1محاسبة متجري\2', t)
    strings.write_text(t)

activity = root / "MainActivity.kt"
t = activity.read_text()
if "override fun attachBaseContext" not in t:
    t = t.replace("import android.os.Bundle", "import android.os.Bundle\nimport android.content.Context\nimport android.content.res.Configuration\nimport java.util.Locale")
    t = t.replace("class MainActivity : ComponentActivity() {", """class MainActivity : ComponentActivity() {
    override fun attachBaseContext(newBase: Context) {
        val locale = Locale("ar")
        Locale.setDefault(locale)
        val config = Configuration(newBase.resources.configuration)
        config.setLocale(locale)
        config.setLayoutDirection(locale)
        super.attachBaseContext(newBase.createConfigurationContext(config))
    }
""")
    activity.write_text(t)

translations = {
    '"Home"':'"الرئيسية"', '"Products"':'"المواد"', '"Analytics"':'"التقارير"',
    '"Inventory"':'"المخزون"', '"Add Product"':'"إضافة مادة"', '"Edit Product"':'"تعديل مادة"',
    '"Add Sale"':'"تسجيل مبيع"', '"Record Sale"':'"حفظ المبيع"', '"Stock In"':'"إدخال بضاعة"',
    '"Today"':'"اليوم"', '"Revenue"':'"إجمالي المبيعات"', '"Profit"':'"الربح"',
    '"Units Sold"':'"الكمية المباعة"', '"Recent Sales"':'"آخر المبيعات"',
    '"Low Stock Alerts"':'"تنبيهات نقص المخزون"', '"No sales yet"':'"لا توجد مبيعات بعد"',
    '"Product *"':'"المادة *"', '"Quantity *"':'"الكمية *"',
    '"Selling Price per Unit *"':'"سعر بيع القطعة *"', '"Notes (optional)"':'"ملاحظات (اختياري)"',
    '"Available"':'"المتوفر"', '"Avg Cost"':'"متوسط التكلفة"',
    '"Sale Preview"':'"ملخص المبيع"', '"Total Revenue"':'"إجمالي المبيع"',
    '"Total Cost (WAC)"':'"إجمالي التكلفة"', '"Margin"':'"هامش الربح"',
    '"Share Report"':'"مشاركة تقرير"', '"No inventory yet"':'"المخزون فارغ"',
    '"Add products and stock to see your inventory"':'"أضف المواد والبضاعة لعرض المخزون"',
    '"Name *"':'"اسم المادة *"', '"Category"':'"التصنيف"',
    '"Product Code"':'"رمز المادة"', '"Unit"':'"وحدة القياس"',
    '"Save Changes"':'"حفظ التعديلات"',
    '"Sales History"':'"سجل المبيعات"',
    '"No sales recorded yet"':'"لم تُسجّل أي مبيعات بعد"',
    '"Tap + to record your first sale"':'"اضغط + لتسجيل أول مبيع"',
    '"Only ${formatQty(product.currentStockQty)} ${product.unit}(s) left"':'"المتبقي: ${formatQty(product.currentStockQty)} ${product.unit}"',
    '"Revenue: ${formatCurrency(dayRevenue)}  ·  Profit: ${formatCurrency(dayProfit)}"':'"المبيعات: ${formatCurrency(dayRevenue)}  ·  الربح: ${formatCurrency(dayProfit)}"',
    '"Inventra"':'"محاسبة متجري"',
    '"Actions"':'"إجراءات"',
    '"Sales"':'"المبيعات"',
    '"Purchases"':'"المشتريات"',
    '"Expenses"':'"المصاريف"',
    '"Debts"':'"الديون"',
    '"Search"':'"بحث"',
    '"Cancel"':'"إلغاء"',
    '"Delete"':'"حذف"',
    '"Confirm"':'"تأكيد"',
    '"Save"':'"حفظ"',
    '"Back"':'"رجوع"',
    '"Settings"':'"الإعدادات"',
    '"All"':'"الكل"',
    '"Date"':'"التاريخ"',
    '"Cost"':'"التكلفة"',
    '"Price"':'"السعر"',
    '"Total"':'"الإجمالي"'
}
for file in root.rglob("*.kt"):
    body = file.read_text()
    for old_text, new_text in translations.items():
        body = body.replace(old_text, new_text)
    file.write_text(body)


dbmodule = Path("inventra/app/src/main/java/com/inventra/app/di/DatabaseModule.kt")
d = dbmodule.read_text()
d = d.replace("saleDao: SaleDao", """saleDao: SaleDao,
        database: InventraDatabase""")
d = d.replace("InventraRepository(productDao, categoryDao, stockPurchaseDao, saleDao)", "InventraRepository(productDao, categoryDao, stockPurchaseDao, saleDao, database)")
if "database: InventraDatabase" not in d:
    raise RuntimeError("Could not inject database into repository provider")
dbmodule.write_text(d)



# Arabic-first colorful dashboard redesign.
dashboard = root / "presentation/dashboard/DashboardScreen.kt"
dashboard.write_text(r'''package com.inventra.app.presentation.dashboard

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddShoppingCart
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.inventra.app.domain.model.Product
import com.inventra.app.domain.model.Sale
import com.inventra.app.ui.components.formatCurrency
import com.inventra.app.ui.components.formatQty
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private val Navy = Color(0xFF172554)
private val Blue = Color(0xFF2563EB)
private val Teal = Color(0xFF0F9D8A)
private val Purple = Color(0xFF7C3AED)
private val AccentPink = Color(0xFFC2186A)
private val Pale = Color(0xFFF4F7FC)

@Composable
fun DashboardScreen(onAddSale: () -> Unit, onStockIn: () -> Unit, viewModel: DashboardViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val recentSales by viewModel.recentSales.collectAsStateWithLifecycle()
    val lowStockProducts by viewModel.lowStockProducts.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { viewModel.loadTodaySummary() }
    val summary = uiState.todaySummary
    Scaffold(containerColor = Pale, floatingActionButton = {
        ExtendedFloatingActionButton(onClick = onAddSale, icon = { Icon(Icons.Default.AddShoppingCart, null) },
            text = { Text("تسجيل مبيع جديد", fontWeight = FontWeight.Bold) },
            containerColor = Blue, contentColor = Color.White)
    }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 14.dp, bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)) {
            item {
                Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(26.dp),
                    colors = CardDefaults.cardColors(containerColor = Navy)) {
                    Column(Modifier.fillMaxWidth().padding(20.dp)) {
                        Text("محاسبة متجري", color = Color.White, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.ExtraBold)
                        Spacer(Modifier.height(5.dp))
                        Text(SimpleDateFormat("EEEE، d MMMM yyyy", Locale("ar")).format(Date()),
                            color = Color.White.copy(alpha = .78f))
                        Spacer(Modifier.height(18.dp))
                        Text("إجمالي مبيعات اليوم", color = Color.White.copy(alpha = .85f))
                        Text(formatCurrency(summary.totalRevenue), color = Color.White,
                            style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                    }
                }
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                    MetricCard("صافي الربح", formatCurrency(summary.totalProfit), Teal, Modifier.weight(1f))
                    MetricCard("القطع المباعة", formatQty(summary.totalUnitsSold), Purple, Modifier.weight(1f))
                }
            }
            item {
                Text("الوصول السريع", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = Navy)
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                    QuickAction("تسجيل مبيع", "أدخل عملية بيع", Blue, Icons.Default.AddShoppingCart, onAddSale, Modifier.weight(1f))
                    QuickAction("إدخال بضاعة", "تحديث المخزون", AccentPink, Icons.Default.Inventory2, onStockIn, Modifier.weight(1f))
                }
            }
            if (lowStockProducts.isNotEmpty()) {
                item { Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Warning, null, tint = AccentPink)
                    Spacer(Modifier.width(7.dp))
                    Text("تنبيهات المخزون", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = Navy)
                } }
                items(lowStockProducts) { LowStockCard(it) }
            }
            item { Text("آخر المبيعات", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = Navy) }
            if (recentSales.isEmpty()) {
                item {
                    Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
                        Column(Modifier.fillMaxWidth().padding(22.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(Icons.Default.TrendingUp, null, tint = Blue, modifier = Modifier.size(34.dp))
                            Spacer(Modifier.height(8.dp))
                            Text("لا توجد مبيعات مسجلة بعد", fontWeight = FontWeight.Bold, color = Navy)
                            Text("ابدأ بتسجيل أول عملية بيع من الزر بالأسفل", color = Color.Gray, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            } else { items(recentSales) { SaleCard(it) } }
        }
    }
}

@Composable
private fun MetricCard(title: String, value: String, color: Color, modifier: Modifier = Modifier) {
    Card(modifier, shape = RoundedCornerShape(20.dp), colors = CardDefaults.cardColors(containerColor = color)) {
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            Text(title, color = Color.White.copy(alpha = .88f))
            Spacer(Modifier.height(8.dp))
            Text(value, color = Color.White, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
        }
    }
}

@Composable
private fun QuickAction(title: String, subtitle: String, color: Color, icon: androidx.compose.ui.graphics.vector.ImageVector, onClick: () -> Unit, modifier: Modifier = Modifier) {
    Card(onClick = onClick, modifier = modifier, shape = RoundedCornerShape(20.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Column(Modifier.fillMaxWidth().padding(14.dp)) {
            Box(Modifier.size(42.dp).background(color.copy(alpha = .12f), RoundedCornerShape(14.dp)), contentAlignment = Alignment.Center) {
                Icon(icon, null, tint = color)
            }
            Spacer(Modifier.height(10.dp))
            Text(title, color = Navy, fontWeight = FontWeight.Bold)
            Text(subtitle, color = Color.Gray, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun LowStockCard(product: Product) {
    Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp), colors = CardDefaults.cardColors(containerColor = Color(0xFFFFECF5))) {
        Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.Warning, null, tint = AccentPink)
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(product.name, fontWeight = FontWeight.Bold, color = Navy)
                Text("المتبقي: ${formatQty(product.currentStockQty)} ${product.unit}", color = Color.DarkGray, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun SaleCard(sale: Sale) {
    Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(sale.productName, color = Navy, fontWeight = FontWeight.Bold)
                Text("${formatQty(sale.quantity)} × ${formatCurrency(sale.sellingPricePerUnit)}", color = Color.Gray, style = MaterialTheme.typography.bodySmall)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(formatCurrency(sale.totalRevenue), color = Navy, fontWeight = FontWeight.Bold)
                Text("ربح ${formatCurrency(sale.profit)}", color = if (sale.profit >= 0) Teal else Color.Red, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
''')



# Manual USD/SYP exchange rate and dual-currency display.
currency_dir = root / "presentation/currency"
currency_dir.mkdir(parents=True, exist_ok=True)
(currency_dir / "CurrencyUi.kt").write_text(r'''package com.inventra.app.presentation.currency

import android.content.Context
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CurrencyExchange
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import java.text.DecimalFormat
import java.text.DecimalFormatSymbols
import java.util.Locale

object CurrencyPrefs {
    private const val PREFS = "accounting_currency_settings"
    private const val KEY_RATE = "usd_to_syp_rate"
    val rateState = mutableStateOf(0.0)
    fun load(context: Context) {
        rateState.value = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_RATE, "0")?.toDoubleOrNull() ?: 0.0
    }
    fun save(context: Context, rate: Double) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_RATE, rate.toString()).apply()
        rateState.value = rate
    }
    fun getRate(): Double = rateState.value
}

@Composable
fun dualCurrencyLabel(amountUsd: Double): String {
    val context = LocalContext.current
    LaunchedEffect(Unit) { CurrencyPrefs.load(context) }
    val rate by CurrencyPrefs.rateState
    val usd = "$" + DecimalFormat("#,##0.##").format(amountUsd)
    return if (rate > 0.0) {
        val syp = DecimalFormat("#,##0", DecimalFormatSymbols(Locale("ar"))).format(amountUsd * rate)
        "$usd  |  $syp ل.س"
    } else "$usd  |  حدّد سعر الصرف"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CurrencySettingsScreen() {
    val context = LocalContext.current
    val rate by CurrencyPrefs.rateState
    var input by remember { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        CurrencyPrefs.load(context)
        if (CurrencyPrefs.getRate() > 0.0) input = CurrencyPrefs.getRate().toString()
    }
    Scaffold(
        containerColor = Color(0xFFF4F7FC),
        topBar = { TopAppBar(title = { Text("إعدادات العملات", fontWeight = FontWeight.Bold) }) }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(18.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Card(shape = RoundedCornerShape(22.dp), colors = CardDefaults.cardColors(containerColor = Color(0xFF172554))) {
                Column(Modifier.fillMaxWidth().padding(20.dp)) {
                    Icon(Icons.Default.CurrencyExchange, null, tint = Color.White, modifier = Modifier.size(32.dp))
                    Spacer(Modifier.height(10.dp))
                    Text("الليرة السورية والدولار", color = Color.White, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text("سيظهر كل مبلغ بالعملتين جنباً إلى جنب وفق السعر الذي تحدده.", color = Color.White.copy(alpha = .8f))
                }
            }
            Text("سعر صرف الدولار", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            OutlinedTextField(
                value = input, onValueChange = { input = it; message = null },
                modifier = Modifier.fillMaxWidth(), label = { Text("كم ليرة سورية تساوي 1 دولار؟") },
                placeholder = { Text("مثال: 13000") }, suffix = { Text("ل.س / $1") },
                singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal)
            )
            Button(onClick = {
                val value = input.trim().replace(",", ".").toDoubleOrNull()
                if (value == null || !value.isFinite() || value <= 0.0) message = "أدخل سعر صرف صحيحاً أكبر من صفر"
                else { CurrencyPrefs.save(context, value); message = "تم حفظ سعر الصرف على هذا الجهاز" }
            }, modifier = Modifier.fillMaxWidth().height(52.dp)) { Text("حفظ سعر الصرف", fontWeight = FontWeight.Bold) }
            if (message != null) Text(message!!, color = if (rate > 0.0) Color(0xFF087F5B) else MaterialTheme.colorScheme.error)
            Card(shape = RoundedCornerShape(18.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
                Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("السعر المعتمد حالياً", fontWeight = FontWeight.Bold)
                    if (rate > 0.0) {
                        Text("1 دولار = ${DecimalFormat("#,##0.##").format(rate)} ليرة سورية", style = MaterialTheme.typography.titleMedium, color = Color(0xFF2563EB), fontWeight = FontWeight.Bold)
                        Text("يمكنك تغييره في أي وقت، وسيُستخدم في عرض القيم المحوّلة.", color = Color.Gray, style = MaterialTheme.typography.bodySmall)
                    } else Text("لم يتم تحديد سعر صرف بعد", color = Color(0xFFB45309))
                }
            }
            Text("الأسعار الأصلية والعمليات المحاسبية تبقى محفوظة بقيمتها الأساسية بالدولار، ويُعرض مقابلها بالليرة حسب السعر الذي تحدده. تغيير السعر لا يغيّر سجلات المبيعات أو الأرباح السابقة.", color = Color.Gray, style = MaterialTheme.typography.bodySmall)
        }
    }
}
''')

dashboard = root / "presentation/dashboard/DashboardScreen.kt"
d = dashboard.read_text()
d = d.replace("import com.inventra.app.ui.components.formatCurrency", "import com.inventra.app.ui.components.formatCurrency\nimport com.inventra.app.presentation.currency.dualCurrencyLabel")
d = d.replace("formatCurrency(summary.totalRevenue)", "dualCurrencyLabel(summary.totalRevenue)")
d = d.replace("formatCurrency(summary.totalProfit)", "dualCurrencyLabel(summary.totalProfit)")
d = d.replace("formatCurrency(sale.totalRevenue)", "dualCurrencyLabel(sale.totalRevenue)")
d = d.replace("formatCurrency(sale.profit)", "dualCurrencyLabel(sale.profit)")
dashboard.write_text(d)

# Apply the selected USD/SYP display consistently to analytics totals and product rankings.
analytics = root / "presentation/analytics/AnalyticsScreen.kt"
a = analytics.read_text()
if "import com.inventra.app.presentation.currency.dualCurrencyLabel" not in a:
    a = a.replace("import com.inventra.app.ui.components.formatCurrency",
                  "import com.inventra.app.ui.components.formatCurrency\nimport com.inventra.app.presentation.currency.dualCurrencyLabel")
for old, new in [
    ("formatCurrency(summary.totalRevenue)", "dualCurrencyLabel(summary.totalRevenue)"),
    ("formatCurrency(summary.totalProfit)", "dualCurrencyLabel(summary.totalProfit)"),
    ("formatCurrency(summary.totalCost)", "dualCurrencyLabel(summary.totalCost)"),
    ("formatCurrency(p.totalRevenue)", "dualCurrencyLabel(p.totalRevenue)"),
    ("formatCurrency(p.totalProfit)", "dualCurrencyLabel(p.totalProfit)"),
    ("formatCurrency(state.summary.totalRevenue)", "dualCurrencyLabel(state.summary.totalRevenue)"),
    ("formatCurrency(state.summary.totalProfit)", "dualCurrencyLabel(state.summary.totalProfit)")
]:
    a = a.replace(old, new)
analytics.write_text(a)

nav = root / "presentation/navigation/NavGraph.kt"
n = nav.read_text()
n = n.replace("import androidx.compose.material.icons.filled.ShoppingBag", "import androidx.compose.material.icons.filled.ShoppingBag\nimport androidx.compose.material.icons.filled.Settings")
n = n.replace("import androidx.compose.material.icons.outlined.ShoppingBag", "import androidx.compose.material.icons.outlined.ShoppingBag\nimport androidx.compose.material.icons.outlined.Settings")
n = n.replace("import com.inventra.app.presentation.stock.StockInScreen", "import com.inventra.app.presentation.stock.StockInScreen\nimport com.inventra.app.presentation.currency.CurrencySettingsScreen")
n = n.replace('    object Inventory : Screen("inventory")', '    object Inventory : Screen("inventory")\n    object Currency : Screen("currency")')
n = n.replace('    BottomNavItem(Screen.Inventory, "Inventory", Icons.Filled.Inventory, Icons.Outlined.Inventory),', '    BottomNavItem(Screen.Inventory, "Inventory", Icons.Filled.Inventory, Icons.Outlined.Inventory),\n    BottomNavItem(Screen.Currency, "العملات", Icons.Filled.Settings, Icons.Outlined.Settings),')
n = n.replace('            composable(Screen.Inventory.route) { InventoryScreen() }', '            composable(Screen.Inventory.route) { InventoryScreen() }\n            composable(Screen.Currency.route) { CurrencySettingsScreen() }')
nav.write_text(n)

print("Customization completed: Arabic colorful dashboard, manual USD/SYP exchange rate, dual currency display and Arabic RTL.")

print("Customization completed: atomic stock/sale writes, validation, Arabic RTL locale, app branding and expanded Arabic labels.")


# Invoices are generated from existing sales records; they never create duplicate sales.
invoice_dir = root / "presentation/invoices"
invoice_dir.mkdir(parents=True, exist_ok=True)

(invoice_dir / "InvoiceViewModel.kt").write_text(r'''package com.inventra.app.presentation.invoices

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.inventra.app.data.repository.InventraRepository
import com.inventra.app.domain.model.Sale
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

@HiltViewModel
class InvoiceViewModel @Inject constructor(repository: InventraRepository) : ViewModel() {
    val sales: StateFlow<List<Sale>> = repository.getRecentSales(200)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
}
''')

(invoice_dir / "InvoiceScreen.kt").write_text(r'''package com.inventra.app.presentation.invoices

import android.content.Intent
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import android.text.Layout
import android.text.StaticLayout
import android.text.TextDirectionHeuristics
import android.text.TextPaint
import android.widget.Toast
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.inventra.app.domain.model.Sale
import com.inventra.app.presentation.currency.dualCurrencyLabel
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InvoiceScreen(onBack: () -> Unit, viewModel: InvoiceViewModel = hiltViewModel()) {
    val context = LocalContext.current
    val sales by viewModel.sales.collectAsStateWithLifecycle()
    val selectedIds = remember { mutableStateListOf<String>() }
    var customer by remember { mutableStateOf("") }
    var invoiceNumber by remember { mutableStateOf("INV-" + System.currentTimeMillis().toString().takeLast(6)) }
    var notes by remember { mutableStateOf("") }
    var savedInvoices by remember { mutableStateOf(emptyList<File>()) }
    val date = remember { SimpleDateFormat("yyyy/MM/dd", Locale("ar")).format(Date()) }
    val selected = sales.filter { selectedIds.contains(it.id) }
    val total = selected.sumOf { it.totalRevenue }
    val totalLabel = dualCurrencyLabel(total)

    LaunchedEffect(Unit) {
        val folder = File(context.filesDir, "invoices")
        savedInvoices = folder.listFiles()?.filter { it.extension.equals("pdf", true) }?.sortedByDescending { it.lastModified() } ?: emptyList()
    }

    fun invoiceText(): String {
        val out = StringBuilder()
        out.append("فاتورة مبيعات\nرقم الفاتورة: ").append(invoiceNumber)
            .append("\nالتاريخ: ").append(date)
            .append("\nاسم العميل: ").append(customer.ifBlank { "—" })
            .append("\n================================\nالمواد المباعة:\n")
        selected.forEachIndexed { index, sale ->
            out.append(index + 1).append(") ").append(sale.productName)
                .append("\nالكمية: ").append(sale.quantity).append(" ").append(sale.productUnit)
                .append("\nسعر الوحدة: $").append(String.format(Locale.US, "%,.2f", sale.sellingPricePerUnit))
                .append("\nالإجمالي: $").append(String.format(Locale.US, "%,.2f", sale.totalRevenue))
                .append("\nرقم سجل المبيع: ").append(sale.id)
                .append("\n--------------------------------\n")
        }
        out.append("إجمالي الفاتورة: ").append(totalLabel)
        if (notes.isNotBlank()) out.append("\nملاحظات: ").append(notes)
        out.append("\nتم إنشاء الفاتورة من عمليات البيع المسجلة في المخزون.")
        return out.toString()
    }

    fun createPdf(): File {
        val content = invoiceText()
        val paint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
            color = android.graphics.Color.DKGRAY
            textSize = 16f
        }
        val layout = StaticLayout.Builder.obtain(content, 0, content.length, paint, 500)
            .setAlignment(Layout.Alignment.ALIGN_OPPOSITE)
            .setTextDirection(TextDirectionHeuristics.RTL)
            .setLineSpacing(7f, 1f).build()
        val doc = PdfDocument()
        val pageHeight = 842
        val top = 115f
        val usable = 680f
        val pages = maxOf(1, kotlin.math.ceil(layout.height / usable).toInt())
        repeat(pages) { index ->
            val page = doc.startPage(PdfDocument.PageInfo.Builder(595, pageHeight, index + 1).create())
            val title = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = android.graphics.Color.rgb(23, 37, 84)
                textSize = 22f
                typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
                textAlign = Paint.Align.RIGHT
            }
            page.canvas.drawText("فاتورة مبيعات - " + invoiceNumber, 540f, 70f, title)
            page.canvas.save()
            page.canvas.clipRect(35f, top, 560f, top + usable)
            page.canvas.translate(45f, top - index * usable)
            layout.draw(page.canvas)
            page.canvas.restore()
            doc.finishPage(page)
        }
        val folder = File(context.filesDir, "invoices").apply { mkdirs() }
        val file = File(folder, "invoice_" + System.currentTimeMillis() + ".pdf")
        file.outputStream().use { doc.writeTo(it) }
        doc.close()
        return file
    }

    fun sharePdf(file: File) {
        try {
            val uri = FileProvider.getUriForFile(context, context.packageName + ".fileprovider", file)
            val send = Intent(Intent.ACTION_SEND).apply {
                type = "application/pdf"
                putExtra(Intent.EXTRA_STREAM, uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            context.startActivity(Intent.createChooser(send, "إرسال الفاتورة"))
        } catch (e: Exception) {
            Toast.makeText(context, "تعذرت مشاركة الفاتورة: " + e.message, Toast.LENGTH_LONG).show()
        }
    }

    Scaffold(topBar = {
        TopAppBar(
            title = { Text("إنشاء فاتورة من المبيعات", fontWeight = FontWeight.Bold) },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "رجوع") } }
        )
    }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
            OutlinedTextField(invoiceNumber, { invoiceNumber = it }, label = { Text("رقم الفاتورة") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(customer, { customer = it }, label = { Text("اسم العميل") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Text("اختر عمليات البيع الفعلية:", fontWeight = FontWeight.Bold)
            if (sales.isEmpty()) {
                Text("لا توجد مبيعات مسجلة. سجّل مبيعاً أولاً ثم أنشئ الفاتورة.")
            } else {
                LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    items(sales, key = { it.id }) { sale ->
                        Card(onClick = {
                            if (selectedIds.contains(sale.id)) selectedIds.remove(sale.id) else selectedIds.add(sale.id)
                        }, shape = RoundedCornerShape(12.dp)) {
                            Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
                                Checkbox(selectedIds.contains(sale.id), { checked ->
                                    if (checked && !selectedIds.contains(sale.id)) selectedIds.add(sale.id)
                                    if (!checked) selectedIds.remove(sale.id)
                                })
                                Column(Modifier.weight(1f)) {
                                    Text(sale.productName, fontWeight = FontWeight.Bold)
                                    Text(sale.quantity.toString() + " " + sale.productUnit + " × " + dualCurrencyLabel(sale.sellingPricePerUnit),
                                        style = MaterialTheme.typography.bodySmall)
                                    Text(SimpleDateFormat("yyyy/MM/dd HH:mm", Locale("ar")).format(Date(sale.date)),
                                        style = MaterialTheme.typography.labelSmall)
                                }
                                Text(dualCurrencyLabel(sale.totalRevenue), fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            }
            OutlinedTextField(notes, { notes = it }, label = { Text("ملاحظات اختيارية") }, modifier = Modifier.fillMaxWidth())
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                Column(Modifier.fillMaxWidth().padding(12.dp)) {
                    Text("عمليات مختارة: " + selected.size)
                    Text("إجمالي الفاتورة: " + totalLabel, fontWeight = FontWeight.ExtraBold,
                        style = MaterialTheme.typography.titleLarge)
                    Text("التاريخ: " + date, style = MaterialTheme.typography.bodySmall)
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = {
                    val clipboard = context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
                    clipboard.setPrimaryClip(android.content.ClipData.newPlainText("فاتورة", invoiceText()))
                    Toast.makeText(context, "تم نسخ الفاتورة", Toast.LENGTH_SHORT).show()
                }, enabled = selected.isNotEmpty(), modifier = Modifier.weight(1f)) { Text("نسخ النص") }
                Button(onClick = {
                    try {
                        val file = createPdf()
                        savedInvoices = listOf(file) + savedInvoices
                        sharePdf(file)
                    } catch (e: Exception) {
                        Toast.makeText(context, "تعذر إنشاء PDF: " + e.message, Toast.LENGTH_LONG).show()
                    }
                }, enabled = selected.isNotEmpty(), modifier = Modifier.weight(1f)) { Text("PDF ومشاركة") }
            }
            if (savedInvoices.isNotEmpty()) {
                Text("الفواتير المحفوظة", fontWeight = FontWeight.Bold)
                savedInvoices.take(3).forEach { file ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(file.nameWithoutExtension, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
                        TextButton(onClick = { sharePdf(file) }) { Text("مشاركة") }
                    }
                }
            }
        }
    }
}
''')

nav = root / "presentation/navigation/NavGraph.kt"
n = nav.read_text()
if "import com.inventra.app.presentation.invoices.InvoiceScreen" not in n:
    n = n.replace("import com.inventra.app.presentation.stock.StockInScreen",
                  "import com.inventra.app.presentation.stock.StockInScreen\nimport com.inventra.app.presentation.invoices.InvoiceScreen")
if 'object Invoices : Screen("invoices")' not in n:
    n = n.replace('    object Inventory : Screen("inventory")',
                  '    object Inventory : Screen("inventory")\n    object Invoices : Screen("invoices")')
if 'BottomNavItem(Screen.Invoices' not in n:
    n = n.replace('    BottomNavItem(Screen.Inventory, "Inventory", Icons.Filled.Inventory, Icons.Outlined.Inventory),',
                  '    BottomNavItem(Screen.Inventory, "Inventory", Icons.Filled.Inventory, Icons.Outlined.Inventory),\n    BottomNavItem(Screen.Invoices, "الفواتير", Icons.Filled.Description, Icons.Outlined.Description),')
if 'composable(Screen.Invoices.route)' not in n:
    n = n.replace('            composable(Screen.Inventory.route) { InventoryScreen() }',
                  '            composable(Screen.Inventory.route) { InventoryScreen() }\n            composable(Screen.Invoices.route) { InvoiceScreen(onBack = { navController.popBackStack() }) }')
n = n.replace("import androidx.compose.material.icons.filled.ShoppingBag",
              "import androidx.compose.material.icons.filled.ShoppingBag\nimport androidx.compose.material.icons.filled.Description")
n = n.replace("import androidx.compose.material.icons.outlined.ShoppingBag",
              "import androidx.compose.material.icons.outlined.ShoppingBag\nimport androidx.compose.material.icons.outlined.Description")
nav.write_text(n)

print("Invoices now select existing recorded sales, display real product/quantity/price values, calculate totals automatically and export/share multi-page PDF or copyable text. No duplicate sale or stock adjustment is created.")


# Ensure both added screens are reachable from the main Arabic navigation bar.
# The earlier translation pass changes the Inventory label before this nav patch runs,
# so match the route rather than relying on the original English label.
nav = root / "presentation/navigation/NavGraph.kt"
n = nav.read_text()
if "BottomNavItem(Screen.Currency" not in n or "BottomNavItem(Screen.Invoices" not in n:
    lines = n.splitlines()
    out = []
    for line in lines:
        out.append(line)
        if "BottomNavItem(Screen.Inventory," in line:
            if "BottomNavItem(Screen.Currency" not in n:
                out.append('    BottomNavItem(Screen.Currency, "العملات", Icons.Filled.Settings, Icons.Outlined.Settings),')
            if "BottomNavItem(Screen.Invoices" not in n:
                out.append('    BottomNavItem(Screen.Invoices, "الفواتير", Icons.Filled.Description, Icons.Outlined.Description),')
    n = "\n".join(out) + "\n"
nav.write_text(n)


# Good Girl app identity and launcher icon (including Android 8+ adaptive icon).
res = Path("inventra/app/src/main/res")
values = res / "values"
values.mkdir(parents=True, exist_ok=True)
strings = values / "strings.xml"
if strings.exists():
    st = strings.read_text()
    st = re.sub(r'(<string name="app_name">).*?(</string>)', r'\1Good Girl\2', st)
    strings.write_text(st)
else:
    strings.write_text('<?xml version="1.0" encoding="utf-8"?>\n<resources><string name="app_name">Good Girl</string></resources>\n')

# Keep the dashboard's visible brand consistent with the launcher name.
dashboard = Path("inventra/app/src/main/java/com/inventra/app/presentation/dashboard/DashboardScreen.kt")
if dashboard.exists():
    d = dashboard.read_text().replace('"محاسبة متجري"', '"Good Girl"')
    dashboard.write_text(d)

(res / "color").mkdir(parents=True, exist_ok=True)
(res / "color" / "goodgirl_background.xml").write_text(
    '<resources><color name="goodgirl_background">#A5005A</color></resources>')

vector = '''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp" android:height="108dp"
    android:viewportWidth="108" android:viewportHeight="108">
    <path android:fillColor="#FFFFFFFF" android:pathData="M38,34 L70,34 L76,44 L76,78 Q76,84 70,84 L38,84 Q32,84 32,78 L32,44 Z"/>
    <path android:fillColor="#FFA5005A" android:pathData="M44,40 L64,40 L68,47 L40,47 Z"/>
    <path android:fillColor="#FFA5005A" android:pathData="M48,29 L60,29 L60,35 L48,35 Z"/>
    <path android:fillColor="#FFA5005A" android:pathData="M52,22 L56,22 L56,30 L52,30 Z"/>
    <path android:fillColor="#FFA5005A" android:pathData="M43,57 C43,51 48,48 54,48 C60,48 65,52 65,58 C65,64 60,68 54,68 C50,68 47,66 45,63 L51,63 C52,64 53,64 54,64 C58,64 60,61 60,58 C60,54 57,52 54,52 C50,52 48,54 48,58 L54,58 L54,62 L43,62 Z"/>
    <path android:fillColor="#FFFFFFFF" android:pathData="M79,23 L82,31 L90,34 L82,37 L79,45 L76,37 L68,34 L76,31 Z"/>
</vector>
'''
(res / "drawable").mkdir(parents=True, exist_ok=True)
(res / "drawable" / "ic_goodgirl_foreground.xml").write_text(vector)

# Legacy launcher fallback.
(res / "mipmap").mkdir(parents=True, exist_ok=True)
(res / "mipmap" / "ic_launcher.xml").write_text(vector)
(res / "mipmap" / "ic_launcher_round.xml").write_text(vector)

adaptive = res / "mipmap-anydpi-v26"
adaptive.mkdir(parents=True, exist_ok=True)
adaptive_xml = '''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/goodgirl_background"/>
    <foreground android:drawable="@drawable/ic_goodgirl_foreground"/>
</adaptive-icon>
'''
(adaptive / "ic_launcher.xml").write_text(adaptive_xml)
(adaptive / "ic_launcher_round.xml").write_text(adaptive_xml)

manifest = Path("inventra/app/src/main/AndroidManifest.xml")
if manifest.exists():
    m = manifest.read_text()
    m = re.sub(r'android:label="@string/app_name"', 'android:label="@string/app_name"', m)
    if 'android:icon="@mipmap/ic_launcher"' not in m:
        m = m.replace('<application', '<application\n        android:icon="@mipmap/ic_launcher"')
    if 'android:roundIcon=' not in m:
        m = m.replace('android:icon="@mipmap/ic_launcher"', 'android:icon="@mipmap/ic_launcher"\n        android:roundIcon="@mipmap/ic_launcher_round"')
    manifest.write_text(m)

print("Good Girl branding and launcher icon resources generated.")


# Restore deleted sales at their historical cost and keep the stock update atomic.
repo_text = repo.read_text()
old_delete = """    suspend fun deleteSale(sale: SaleEntity) {
        // Restore stock quantity when a sale is deleted; avg cost is unchanged
        val product = productDao.getProductById(sale.productId) ?: return
        productDao.updateStockStats(sale.productId, product.currentStockQty + sale.quantity, product.currentAvgCost)
        saleDao.deleteSale(sale)
    }"""
new_delete = """    suspend fun deleteSale(sale: SaleEntity) {
        database.withTransaction {
            val product = productDao.getProductById(sale.productId) ?: return@withTransaction
            val restoredQty = product.currentStockQty + sale.quantity
            val restoredValue = product.currentStockQty * product.currentAvgCost +
                sale.quantity * sale.avgCostAtSale
            val restoredAvgCost = if (restoredQty > 0.0) restoredValue / restoredQty else 0.0
            productDao.updateStockStats(sale.productId, restoredQty, restoredAvgCost)
            saleDao.deleteSale(sale)
        }
    }"""
if old_delete in repo_text:
    repo_text = repo_text.replace(old_delete, new_delete)
else:
    raise RuntimeError("Expected upstream deleteSale implementation not found")
repo.write_text(repo_text)

# Configure FileProvider so generated invoice PDFs can actually be shared.
res_root = Path("inventra/app/src/main/res")
xml_dir = res_root / "xml"
xml_dir.mkdir(parents=True, exist_ok=True)
(xml_dir / "file_paths.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<paths xmlns:android="http://schemas.android.com/apk/res/android">
    <files-path name="invoice_files" path="invoices/" />
</paths>
""")
manifest = Path("inventra/app/src/main/AndroidManifest.xml")
m = manifest.read_text()
if "androidx.core.content.FileProvider" not in m:
    provider = '''
        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="${applicationId}.fileprovider"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data
                android:name="android.support.FILE_PROVIDER_PATHS"
                android:resource="@xml/file_paths" />
        </provider>
'''
    m = m.replace("    </application>", provider + "    </application>")
manifest.write_text(m)
print("Invoice PDF sharing configured and historical-cost sale deletion made atomic.")


# Persistent original multi-item sales invoices (not PDFs assembled from past sales).
entity_dir = root / "data/local/entity"
dao_dir = root / "data/local/dao"
entity_dir.mkdir(parents=True, exist_ok=True)
dao_dir.mkdir(parents=True, exist_ok=True)

(entity_dir / "InvoiceEntity.kt").write_text(r'''package com.inventra.app.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey
import java.util.UUID

@Entity(tableName = "invoices")
data class InvoiceEntity(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val invoiceNumber: String,
    val customerName: String = "",
    val date: Long = System.currentTimeMillis(),
    val totalRevenue: Double,
    val totalCost: Double,
    val totalProfit: Double,
    val paidAmount: Double,
    val remainingAmount: Double,
    val notes: String = ""
)
''')

(entity_dir / "InvoiceLineEntity.kt").write_text(r'''package com.inventra.app.data.local.entity

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey
import java.util.UUID

@Entity(
    tableName = "invoice_lines",
    foreignKeys = [ForeignKey(
        entity = InvoiceEntity::class,
        parentColumns = ["id"],
        childColumns = ["invoiceId"],
        onDelete = ForeignKey.CASCADE
    )],
    indices = [Index("invoiceId"), Index("productId")]
)
data class InvoiceLineEntity(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val invoiceId: String,
    val productId: String,
    val productNameSnapshot: String,
    val unitSnapshot: String,
    val quantity: Double,
    val sellingPricePerUnit: Double,
    val avgCostAtSale: Double,
    val totalRevenue: Double,
    val totalCost: Double,
    val profit: Double,
    val saleId: String
)
''')

(dao_dir / "InvoiceDao.kt").write_text(r'''package com.inventra.app.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import com.inventra.app.data.local.entity.InvoiceEntity
import com.inventra.app.data.local.entity.InvoiceLineEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface InvoiceDao {
    @Insert
    suspend fun insertInvoice(invoice: InvoiceEntity)

    @Insert
    suspend fun insertLines(lines: List<InvoiceLineEntity>)

    @Query("SELECT * FROM invoices ORDER BY date DESC")
    fun observeInvoices(): Flow<List<InvoiceEntity>>

    @Query("SELECT * FROM invoice_lines WHERE invoiceId = :invoiceId ORDER BY rowid ASC")
    suspend fun getLines(invoiceId: String): List<InvoiceLineEntity>

    @Query("SELECT * FROM invoices WHERE id = :id LIMIT 1")
    suspend fun getInvoice(id: String): InvoiceEntity?
}
''')

# Add Room entities and a non-destructive 1 -> 2 migration.
db = root / "data/local/InventraDatabase.kt"
d = db.read_text()
d = d.replace("import com.inventra.app.data.local.entity.SaleEntity",
              "import com.inventra.app.data.local.entity.SaleEntity\nimport com.inventra.app.data.local.entity.InvoiceEntity\nimport com.inventra.app.data.local.entity.InvoiceLineEntity\nimport com.inventra.app.data.local.dao.InvoiceDao")
d = d.replace("        SaleEntity::class",
              "        SaleEntity::class,\n        InvoiceEntity::class,\n        InvoiceLineEntity::class")
d = d.replace("version = 1,", "version = 2,")
d = d.replace("    abstract fun saleDao(): SaleDao",
              "    abstract fun saleDao(): SaleDao\n    abstract fun invoiceDao(): InvoiceDao")
if "MIGRATION_1_2" not in d:
    d = d.replace("    companion object {\n        const val DATABASE_NAME",
'''    companion object {
        val MIGRATION_1_2 = object : androidx.room.migration.Migration(1, 2) {
            override fun migrate(db: androidx.sqlite.db.SupportSQLiteDatabase) {
                db.execSQL("""CREATE TABLE IF NOT EXISTS invoices (
                    id TEXT NOT NULL PRIMARY KEY,
                    invoiceNumber TEXT NOT NULL,
                    customerName TEXT NOT NULL,
                    date INTEGER NOT NULL,
                    totalRevenue REAL NOT NULL,
                    totalCost REAL NOT NULL,
                    totalProfit REAL NOT NULL,
                    paidAmount REAL NOT NULL,
                    remainingAmount REAL NOT NULL,
                    notes TEXT NOT NULL
                )""")
                db.execSQL("""CREATE TABLE IF NOT EXISTS invoice_lines (
                    id TEXT NOT NULL PRIMARY KEY,
                    invoiceId TEXT NOT NULL,
                    productId TEXT NOT NULL,
                    productNameSnapshot TEXT NOT NULL,
                    unitSnapshot TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    sellingPricePerUnit REAL NOT NULL,
                    avgCostAtSale REAL NOT NULL,
                    totalRevenue REAL NOT NULL,
                    totalCost REAL NOT NULL,
                    profit REAL NOT NULL,
                    saleId TEXT NOT NULL,
                    FOREIGN KEY(invoiceId) REFERENCES invoices(id) ON UPDATE NO ACTION ON DELETE CASCADE
                )""")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_invoice_lines_invoiceId ON invoice_lines(invoiceId)")
                db.execSQL("CREATE INDEX IF NOT EXISTS index_invoice_lines_productId ON invoice_lines(productId)")
            }
        }
        const val DATABASE_NAME''')
db.write_text(d)

# Keep all existing data and register the explicit migration in Room.
module = Path("inventra/app/src/main/java/com/inventra/app/di/DatabaseModule.kt")
m = module.read_text()
m = m.replace("            .build()",
              "            .addMigrations(InventraDatabase.MIGRATION_1_2)\n            .build()")
if "InvoiceDao" not in m:
    m = m.replace("import com.inventra.app.data.local.dao.CategoryDao",
                  "import com.inventra.app.data.local.dao.CategoryDao\nimport com.inventra.app.data.local.dao.InvoiceDao")
    m = m.replace("    @Provides fun provideSaleDao(db: InventraDatabase): SaleDao = db.saleDao()",
                  "    @Provides fun provideSaleDao(db: InventraDatabase): SaleDao = db.saleDao()\n    @Provides fun provideInvoiceDao(db: InventraDatabase): InvoiceDao = db.invoiceDao()")
    m = m.replace("        saleDao: SaleDao,",
                  "        saleDao: SaleDao,\n        invoiceDao: InvoiceDao,")
    m = m.replace("InventraRepository(productDao, categoryDao, stockPurchaseDao, saleDao, database)",
                  "InventraRepository(productDao, categoryDao, stockPurchaseDao, saleDao, database, invoiceDao)")
module.write_text(m)

# Transactionally create invoice, invoice lines, historical sale records and stock deductions.
repo_file = root / "data/repository/InventraRepository.kt"
r = repo_file.read_text()
if "import com.inventra.app.data.local.dao.InvoiceDao" not in r:
    r = r.replace("import com.inventra.app.data.local.dao.CategoryDao",
                  "import com.inventra.app.data.local.dao.CategoryDao\nimport com.inventra.app.data.local.dao.InvoiceDao")
    r = r.replace("import com.inventra.app.data.local.entity.CategoryEntity",
                  "import com.inventra.app.data.local.entity.CategoryEntity\nimport com.inventra.app.data.local.entity.InvoiceEntity\nimport com.inventra.app.data.local.entity.InvoiceLineEntity")
    r = r.replace("import java.util.Locale", "import java.util.Locale\nimport java.util.UUID")
    r = r.replace("    private val database: InventraDatabase\n)",
                  "    private val database: InventraDatabase,\n    private val invoiceDao: InvoiceDao\n)")
    marker = "    // ── Products ─"
    method = '''
    data class InvoiceLineDraft(
        val productId: String,
        val quantity: Double,
        val sellingPricePerUnit: Double
    )

    val invoices = invoiceDao.observeInvoices()

    suspend fun createSalesInvoice(
        invoiceNumber: String,
        customerName: String,
        paidAmount: Double,
        date: Long,
        notes: String,
        lines: List<InvoiceLineDraft>
    ): Result<String> {
        if (invoiceNumber.isBlank()) return Result.failure(IllegalArgumentException("رقم الفاتورة مطلوب"))
        if (lines.isEmpty()) return Result.failure(IllegalArgumentException("أضف مادة واحدة على الأقل"))
        if (!paidAmount.isFinite() || paidAmount < 0.0)
            return Result.failure(IllegalArgumentException("المبلغ المدفوع غير صالح"))
        return database.withTransaction {
            val grouped = lines.groupBy { it.productId }
            val products = mutableMapOf<String, ProductEntity>()
            for ((productId, productLines) in grouped) {
                val product = productDao.getProductById(productId)
                    ?: return@withTransaction Result.failure(IllegalArgumentException("إحدى المواد لم تعد موجودة"))
                val required = productLines.sumOf { it.quantity }
                if (productLines.any { !it.quantity.isFinite() || it.quantity <= 0.0 ||
                        !it.sellingPricePerUnit.isFinite() || it.sellingPricePerUnit < 0.0 })
                    return@withTransaction Result.failure(IllegalArgumentException("تحقق من الكميات وأسعار البيع"))
                if (product.currentStockQty < required)
                    return@withTransaction Result.failure(IllegalArgumentException("المخزون غير كافٍ للمادة: ${product.name}"))
                products[productId] = product
            }

            val expectedRevenue = lines.sumOf { it.quantity * it.sellingPricePerUnit }
            if (!expectedRevenue.isFinite() || paidAmount > expectedRevenue)
                return@withTransaction Result.failure(IllegalArgumentException("المبلغ المدفوع أكبر من إجمالي الفاتورة أو الإجمالي غير صالح"))

            val invoiceId = UUID.randomUUID().toString()
            val lineEntities = mutableListOf<InvoiceLineEntity>()
            var revenue = 0.0
            var cost = 0.0
            for (line in lines) {
                val product = products.getValue(line.productId)
                val lineRevenue = line.quantity * line.sellingPricePerUnit
                val lineCost = line.quantity * product.currentAvgCost
                val saleId = UUID.randomUUID().toString()
                saleDao.insertSale(SaleEntity(
                    id = saleId,
                    productId = product.id,
                    quantity = line.quantity,
                    sellingPricePerUnit = line.sellingPricePerUnit,
                    totalRevenue = lineRevenue,
                    avgCostAtSale = product.currentAvgCost,
                    totalCost = lineCost,
                    profit = lineRevenue - lineCost,
                    date = date,
                    notes = "فاتورة $invoiceNumber"
                ))
                lineEntities += InvoiceLineEntity(
                    invoiceId = invoiceId,
                    productId = product.id,
                    productNameSnapshot = product.name,
                    unitSnapshot = product.unit,
                    quantity = line.quantity,
                    sellingPricePerUnit = line.sellingPricePerUnit,
                    avgCostAtSale = product.currentAvgCost,
                    totalRevenue = lineRevenue,
                    totalCost = lineCost,
                    profit = lineRevenue - lineCost,
                    saleId = saleId
                )
                revenue += lineRevenue
                cost += lineCost
            }
            invoiceDao.insertInvoice(InvoiceEntity(
                id = invoiceId,
                invoiceNumber = invoiceNumber,
                customerName = customerName,
                date = date,
                totalRevenue = revenue,
                totalCost = cost,
                totalProfit = revenue - cost,
                paidAmount = paidAmount,
                remainingAmount = revenue - paidAmount,
                notes = notes
            ))
            invoiceDao.insertLines(lineEntities)
            for ((productId, product) in products) {
                val sold = grouped.getValue(productId).sumOf { it.quantity }
                productDao.updateStockStats(productId, product.currentStockQty - sold, product.currentAvgCost)
            }
            Result.success(invoiceId)
        }
    }

'''
    r = r.replace(marker, method + marker)
repo_file.write_text(r)

# A real invoice-entry screen: choose products, enter quantities and manual prices, then save once.
invoice_dir = root / "presentation/invoices"
(invoice_dir / "InvoiceViewModel.kt").write_text(r'''package com.inventra.app.presentation.invoices

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.inventra.app.data.repository.InventraRepository
import com.inventra.app.domain.model.Product
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed class InvoiceSaveResult {
    object Idle : InvoiceSaveResult()
    data class Success(val invoiceId: String) : InvoiceSaveResult()
    data class Error(val message: String) : InvoiceSaveResult()
}

@HiltViewModel
class InvoiceViewModel @Inject constructor(
    private val repository: InventraRepository
) : ViewModel() {
    val products: StateFlow<List<Product>> = repository.allProducts
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
    private val _result = MutableStateFlow<InvoiceSaveResult>(InvoiceSaveResult.Idle)
    val result: StateFlow<InvoiceSaveResult> = _result.asStateFlow()

    fun save(number: String, customer: String, paid: Double, date: Long, notes: String,
             lines: List<InventraRepository.InvoiceLineDraft>) {
        viewModelScope.launch {
            repository.createSalesInvoice(number, customer, paid, date, notes, lines).fold(
                onSuccess = { _result.value = InvoiceSaveResult.Success(it) },
                onFailure = { _result.value = InvoiceSaveResult.Error(it.message ?: "تعذر حفظ الفاتورة") }
            )
        }
    }
    fun reset() { _result.value = InvoiceSaveResult.Idle }
}
''')

(invoice_dir / "InvoiceScreen.kt").write_text(r'''package com.inventra.app.presentation.invoices

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.inventra.app.data.repository.InventraRepository
import com.inventra.app.domain.model.Product
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InvoiceScreen(onBack: () -> Unit, viewModel: InvoiceViewModel = hiltViewModel()) {
    val products by viewModel.products.collectAsStateWithLifecycle()
    val result by viewModel.result.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }
    val quantities = remember { mutableStateMapOf<String, String>() }
    val prices = remember { mutableStateMapOf<String, String>() }
    var customer by remember { mutableStateOf("") }
    var number by remember { mutableStateOf("GG-" + System.currentTimeMillis().toString().takeLast(8)) }
    var paid by remember { mutableStateOf("") }
    var notes by remember { mutableStateOf("") }
    val selected = products.filter { (quantities[it.id]?.toDoubleOrNull() ?: 0.0) > 0.0 }
    val total = selected.sumOf { p -> (quantities[p.id]?.toDoubleOrNull() ?: 0.0) * (prices[p.id]?.toDoubleOrNull() ?: 0.0) }

    LaunchedEffect(result) {
        when (val r = result) {
            is InvoiceSaveResult.Success -> { snackbar.showSnackbar("تم حفظ الفاتورة بنجاح"); viewModel.reset(); onBack() }
            is InvoiceSaveResult.Error -> { snackbar.showSnackbar(r.message); viewModel.reset() }
            else -> Unit
        }
    }
    Scaffold(
        topBar = { TopAppBar(
            title = { Text("فاتورة مبيعات جديدة", fontWeight = FontWeight.Bold) },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "رجوع") } }
        ) },
        snackbarHost = { SnackbarHost(snackbar) }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(number, { number = it }, label = { Text("رقم الفاتورة") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(customer, { customer = it }, label = { Text("اسم العميل") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Text("مواد الفاتورة", fontWeight = FontWeight.Bold)
            LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(7.dp)) {
                items(products, key = { it.id }) { p ->
                    InvoiceProductRow(p, quantities[p.id] ?: "", { quantities[p.id] = it },
                        prices[p.id] ?: "", { prices[p.id] = it })
                }
            }
            OutlinedTextField(paid, { paid = it }, label = { Text("المبلغ المدفوع") },
                modifier = Modifier.fillMaxWidth(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), singleLine = true)
            OutlinedTextField(notes, { notes = it }, label = { Text("ملاحظات") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Card(shape = RoundedCornerShape(14.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                Column(Modifier.fillMaxWidth().padding(12.dp)) {
                    Text("عدد المواد: ${selected.size}")
                    Text("إجمالي الفاتورة: " + String.format(Locale.US, "%.2f", total), fontWeight = FontWeight.ExtraBold)
                    Text("المتبقي: " + String.format(Locale.US, "%.2f", (total - (paid.toDoubleOrNull() ?: 0.0)).coerceAtLeast(0.0)))
                }
            }
            Button(
                onClick = {
                    val lines = selected.map { p ->
                        InventraRepository.InvoiceLineDraft(p.id, quantities[p.id]?.toDoubleOrNull() ?: 0.0,
                            prices[p.id]?.toDoubleOrNull() ?: 0.0)
                    }
                    viewModel.save(number, customer, paid.toDoubleOrNull() ?: 0.0,
                        System.currentTimeMillis(), notes, lines)
                },
                enabled = selected.isNotEmpty() && result !is InvoiceSaveResult.Success,
                modifier = Modifier.fillMaxWidth()
            ) { Text("حفظ الفاتورة وتحديث المخزون") }
        }
    }
}

@Composable
private fun InvoiceProductRow(product: Product, quantity: String, onQuantity: (String) -> Unit,
                              price: String, onPrice: (String) -> Unit) {
    Card(shape = RoundedCornerShape(12.dp)) {
        Column(Modifier.fillMaxWidth().padding(10.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text(product.name + "  •  المتوفر: " + String.format(Locale.US, "%,.2f", product.currentStockQty),
                fontWeight = FontWeight.Bold)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(quantity, onQuantity, label = { Text("الكمية") }, modifier = Modifier.weight(1f),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), singleLine = true)
                OutlinedTextField(price, onPrice, label = { Text("سعر الوحدة") }, modifier = Modifier.weight(1f),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), singleLine = true)
            }
        }
    }
}
''')

print("Original invoice persistence, Room migration, transactional multi-line sale/stock updates, and invoice-entry UI generated.")
