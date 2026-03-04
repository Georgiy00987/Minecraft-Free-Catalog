import os
import aiohttp
from errors import CryptoBotEnvError

class CryptoBot():
	def __init__(self, timeout=360):
		api_token = os.getenv("CRYPTOBOT_TOKEN")

		if not api_token:
			raise CryptoBotEnvError()

		self.base_url = "https://pay.crypt.bot/api"
		self.headers = {"Crypto-Pay-API-Token": api_token}
		self.timeout = aiohttp.ClientTimeout(total=timeout)
	
	async def get_me(self):
		async with aiohttp.ClientSession(
			headers=self.headers, timeout=self.timeout
		) as session:
			resp = await session.get(f"{self.base_url}/getMe")
			return await resp.json()
	
	async def check(self):
		result = await self.get_me()
		
		if not result['ok']:
			raise ConnectionError("Неверный токен [CryptoBot]")
	
	async def create_invoice(self, amount, asset):
		try:
			async with aiohttp.ClientSession(
				headers=self.headers, timeout=self.timeout
			) as session:
				data = {
					"amount": amount,
					"asset": asset,
					"expires_in": 3600
				}
				resp = await session.post(f'{self.base_url}/createinvoice', data=data)
			return await resp.json()
		except:
			return {'ok': False}
	
	async def delete_invoice(self, invoice_id: int) -> bool:
		try:
			async with aiohttp.ClientSession(
				headers=self.headers, timeout=self.timeout
			) as session:
				data = {
					"invoice_id": invoice_id
				}
				resp = await session.post(f"{self.base_url}/deleteInvoice", data=data)
				result = await resp.json()
				
				if result.get("ok") and result["result"]["status"] == "cancelled":
					return True
				return False
		except Exception:
			return False
	
	async def check_invoice(self, invoice_id: int):
		async with aiohttp.ClientSession(
			headers=self.headers, timeout=self.timeout
		) as session:
			data = {
				"invoice_ids": [invoice_id],
				"count": 1
			}
			resp = await session.get(f"{self.base_url}/getInvoices", data=data)
			result = await resp.json()
			
			if result.get("ok") and  result['result']['items'][0]['status'] == "paid":
				return True
			return False
	
	async def get_balance(self, asset: str = None):
		async with aiohttp.ClientSession(
			headers=self.headers, timeout=self.timeout
		) as session:
			resp = await session.get(f"{self.base_url}/getBalance")
			result = await resp.json()

			if not result.get("ok", None):
				return None
			
			balances = result["result"]

			if asset:
				for item in balances:
					if item["currency_code"].upper() == asset.upper():
						return float(item["available"])
				return 0.0
			return balances
	
	async def invoices(self, asset="USDT", status="active", count=1000):
		async with aiohttp.ClientSession(
			headers=self.headers, timeout=self.timeout
		) as session:
			data = {
				"asset": asset,
				"status": status,
				"count": count
			}
			resp = await session.get(f"{self.base_url}/getInvoices", data=data)
			result = await resp.json()
			
			if not result.get("ok", None):
				return []
			
			return result['result']['items']