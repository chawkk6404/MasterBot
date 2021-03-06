import pytz
from datetime import datetime
import time
from typing import Optional

import discord
from discord.ext import commands


class WeatherUtils:
    @staticmethod
    async def build_current_embed(data, ctx, self) -> discord.Embed:
        embed = discord.Embed(
            title=f'{data.get("location").get("name")}, {data.get("location").get("region")}, {data.get("location").get("country")}',
        )
        tz = pytz.timezone(data["location"]["tz_id"])
        local_time = datetime.fromtimestamp(data["location"]["localtime_epoch"], tz)
        local_time = local_time.strftime("%H:%M")
        embed.set_footer(text=f"Local Time: {local_time}")
        temp_unit = self.temp_units.get(ctx.guild.id) or "C"
        speed_unit = self.speed_units.get(ctx.guild.id) or "kph"
        data = data.get("current")
        if temp_unit == "C":
            temp = data.get("temp_c")
            feels_like = data.get("feelslike_c")
        else:
            temp = data.get("temp_f")
            feels_like = data.get("feelslike_f")
        embed.add_field(name="Temperature", value=f"{temp} {temp_unit}")
        embed.add_field(name="Feels Like", value=f"{feels_like} {temp_unit}")
        embed.add_field(name="Weather", value=data.get("condition").get("text"))
        if speed_unit == "kph":
            speed = data.get("wind_kph")
            visibility = str(data.get("vis_km")) + " km"
        else:
            speed = data.get("wind_mph")
            visibility = str(data.get("vis_miles")) + " miles"
        embed.add_field(name="Wind Direction", value=data.get("wind_dir"))
        embed.add_field(name="Wind Speed", value=f"{speed} {speed_unit}")
        embed.add_field(name="Visibility", value=visibility)
        last_updated_at = int(data.get("last_updated_epoch"))
        embed.add_field(name="Last Updated At", value=f"<t:{last_updated_at}:R>")
        embed.set_thumbnail(url="https:" + data.get("condition").get("icon"))
        return embed

    @staticmethod
    async def build_forecast_embed(data, ctx, self, days) -> Optional[discord.Embed]:
        days -= 1
        embed = discord.Embed(
            title=f'{data.get("location").get("name")}, {data.get("location").get("region")}, {data.get("location").get("country")}'
        )
        try:
            data = data.get("forecast").get("forecastday")[days]
        except IndexError:
            if isinstance(ctx, commands.Context):
                await ctx.send(
                    f"I couldn't find anything for {days} days away. Try another number."
                )
            else:
                await ctx.response.send_message(
                    f"I couldn't find anything for {days} days away. Try another number."
                )
            return
        date = round(
            time.mktime(datetime.fromtimestamp(data.get("date_epoch")).timetuple())
        )
        embed.add_field(name="Forecast Date", value=f"<t:{date}:D>")
        temp_unit = self.temp_units.get(ctx.guild.id) or "C"
        speed_unit = self.speed_units.get(ctx.guild.id) or "kph"
        day = data.get("day")
        weather = day.get("condition").get("text")
        embed.add_field(name="Weather", value=weather)
        embed.set_thumbnail(url="https:" + day.get("condition").get("icon"))
        if temp_unit == "C":
            day_max_temp = str(day.get("maxtemp_c")) + " C"
            day_min_temp = str(day.get("mintemp_c")) + " C"
        else:
            day_max_temp = str(day.get("maxtemp_f")) + " F"
            day_min_temp = str(day.get("mintemp_f")) + " F"
        embed.add_field(name="High", value=day_max_temp)
        embed.add_field(name="Low", value=day_min_temp)
        if speed_unit == "kph":
            wind = str(day.get("maxwind_kph")) + " kph"
            precip = str(day.get("totalprecip_mm")) + " mm"
            vis = str(day.get("avgvis_km")) + " km"
        else:
            wind = str(day.get("maxwind_mph")) + " mph"
            precip = str(day.get("totalprecip_in")) + " in"
            vis = str(day.get("avgvis_miles")) + " miles"
        embed.add_field(name="Wind", value=wind)
        embed.add_field(name="Visibility", value=vis)
        embed.add_field(name="Rain", value=precip)
        rain_chance = str(day.get("daily_chance_of_rain")) + "%"
        snow_chance = str(day.get("daily_chance_of_snow")) + "%"
        embed.add_field(name="Chance of Rain", value=rain_chance)
        embed.add_field(name="Chance of Snow", value=snow_chance)
        sunrise = data.get("astro").get("sunrise")
        sunset = data.get("astro").get("sunset")
        embed.add_field(name="Sunrise", value=sunrise)
        embed.add_field(name="Sunset", value=sunset)
        moon = data.get("astro").get("moon_phase")
        embed.add_field(name="Moon Phase", value=moon)
        return embed

    @staticmethod
    async def build_search_embed(data: dict, ctx, index) -> Optional[discord.Embed]:
        index -= 1
        try:
            data = data[index]
        except KeyError:
            if isinstance(ctx, commands.Context):
                await ctx.send(
                    "I couldn't find that result. Make sure that city exists."
                )
            else:
                ctx.response.send_message(
                    "I couldn't find that result. Make sure that city exists."
                )
            return
        embed = discord.Embed(title=data.get("name"))
        embed.add_field(name="Region", value=data.get("region"), inline=False)
        embed.add_field(name="Country", value=data.get("country"))
        embed.add_field(name="Latitude", value=data.get("lat"), inline=False)
        embed.add_field(name="Longitude", value=data.get("lon"))
        return embed

    @staticmethod
    async def build_tz_embed(data) -> discord.Embed:
        embed = discord.Embed(
            title=f'{data.get("location").get("name")}, {data.get("location").get("region")}, {data.get("location").get("country")}'
        )
        embed.add_field(name="Timezone ID", value=data.get("location").get("tz_id"))
        embed.add_field(name="Local Time", value=data.get("location").get("localtime"))
        return embed
