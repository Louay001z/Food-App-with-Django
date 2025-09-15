import json
from channels.generic.websocket import AsyncWebsocketConsumer # type: ignore
from channels.db import database_sync_to_async # type: ignore
from .models import Order

class OrderConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.order_group_name = f'order_{self.order_id}'

        await self.channel_layer.group_add(
            self.order_group_name,
            self.channel_name
        )
        await self.accept()

        order = await self.get_order()
        if order:
            await self.send(text_data=json.dumps({
                'status': order.status
            }))
        else:
            await self.close()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.order_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        pass

    async def order_update(self, event):
        await self.send(text_data=json.dumps({
            'status': event['status']
        }))

    @database_sync_to_async
    def get_order(self):
        try:
            return Order.objects.get(id=self.order_id)
        except Order.DoesNotExist:
            return None