"""
数据相关 API 路由
提供股票数据、市场数据、批量数据查询接口
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from models import (
    APIResponse,
    BatchDataRequest,
    MarketDataRequest,
    StockDataRequest,
)

router = APIRouter()


@router.get("/stock/{symbol}", response_model=APIResponse)
async def get_stock_data(
    symbol: str,
    market: str = Query("us", description="市场类型 (us, cn, hk)"),
    timeframe: str = Query("daily", description="时间周期 (1m, 5m, 1h, daily, weekly)"),
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=10000, description="返回条数限制"),
    request: Request = None,
) -> APIResponse:
    """
    获取单只股票的历史数据

    - **symbol**: 股票代码，如 AAPL, 000001
    - **market**: 市场类型 us/cn/hk
    - **timeframe**: 时间周期
    - **start_date**: 开始日期 (可选)
    - **end_date**: 结束日期 (可选)
    - **limit**: 返回数据条数限制 (默认100，最大10000)
    """
    try:
        client = request.app.state.vprism_client

        # 构建查询
        query = client.query().asset(symbol).market(market).timeframe(timeframe).limit(limit)

        if start_date:
            query = query.start_date(start_date)
        if end_date:
            query = query.end_date(end_date)

        # 执行查询
        result = await client.execute_async(query.build())

        return APIResponse(
            success=True,
            data=result.model_dump() if hasattr(result, "model_dump") else result,
            message=f"成功获取 {symbol} 的数据",
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stock", response_model=APIResponse)
async def get_stock_data_post(
    request_data: StockDataRequest,
    request: Request = None,
) -> APIResponse:
    """
    获取单只股票数据的 POST 接口

    提供更灵活的参数配置和批量查询支持
    """
    try:
        client = request.app.state.vprism_client

        query = client.query().asset(request_data.symbol).market(request_data.market).timeframe(request_data.timeframe).limit(request_data.limit)

        if request_data.start_date:
            query = query.start_date(request_data.start_date)
        if request_data.end_date:
            query = query.end_date(request_data.end_date)

        result = await client.execute_async(query.build())

        return APIResponse(
            success=True,
            data=result.model_dump() if hasattr(result, "model_dump") else result,
            message=f"成功获取 {request_data.symbol} 的数据",
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/market", response_model=APIResponse)
async def get_market_data(
    request_data: MarketDataRequest,
    request: Request = None,
) -> APIResponse:
    """
    获取市场数据

    可以获取整个市场或特定股票列表的数据
    """
    try:
        client = request.app.state.vprism_client

        # 构建基础查询
        query = client.query().market(request_data.market).timeframe(request_data.timeframe)

        if request_data.start_date:
            query = query.start_date(request_data.start_date)
        if request_data.end_date:
            query = query.end_date(request_data.end_date)

        # 如果有指定股票列表
        if request_data.symbols:
            results = []
            for symbol in request_data.symbols:
                symbol_query = query.asset(symbol).build()
                result = await client.execute_async(symbol_query)
                results.append(
                    {
                        "symbol": symbol,
                        "data": result.model_dump() if hasattr(result, "model_dump") else result,
                    }
                )

            return APIResponse(
                success=True,
                data=results,
                message=f"成功获取 {len(request_data.symbols)} 只股票的数据",
            )
        else:
            # 获取整个市场数据（简化实现）
            result = await client.execute_async(query.build())
            return APIResponse(
                success=True,
                data=result.model_dump() if hasattr(result, "model_dump") else result,
                message=f"成功获取 {request_data.market} 市场的数据",
            )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch", response_model=APIResponse)
async def get_batch_data(
    request_data: BatchDataRequest,
    background_tasks: BackgroundTasks,
    request: Request = None,
) -> APIResponse:
    """
    批量获取多只股票数据

    - 支持同步和异步处理
    - 最大支持100个查询
    """
    try:
        client = request.app.state.vprism_client

        if len(request_data.queries) > 100:
            raise HTTPException(status_code=400, detail="单次查询数量不能超过100个")

        queries = []
        for query_req in request_data.queries:
            query = client.query().asset(query_req.symbol).market(query_req.market).timeframe(query_req.timeframe).limit(query_req.limit)

            if query_req.start_date:
                query = query.start_date(query_req.start_date)
            if query_req.end_date:
                query = query.end_date(query_req.end_date)

            queries.append(query.build())

        if request_data.async_processing:
            # 异步处理（后台任务）
            background_tasks.add_task(_process_batch_async, client, queries, request)
            return APIResponse(
                success=True,
                data={"status": "processing", "queries": len(queries)},
                message="批量查询已提交，正在后台处理",
            )
        else:
            # 同步处理
            results = await client.batch_get_async(queries)

            response_data = []
            for i, result in enumerate(results):
                response_data.append(
                    {
                        "query": request_data.queries[i].model_dump(),
                        "data": result.model_dump() if hasattr(result, "model_dump") else result,
                    }
                )

            return APIResponse(
                success=True,
                data=response_data,
                message=f"成功处理 {len(results)} 个查询",
            )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/symbols", response_model=APIResponse)
async def list_symbols(
    market: str = Query("us", description="市场类型"),
    request: Request = None,
) -> APIResponse:
    """
    获取指定市场的股票代码列表
    """
    try:
        # 这里应该调用客户端的资产发现功能
        # 暂时返回示例数据
        symbols = {
            "us": ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA", "META", "AMZN"],
            "cn": ["000001", "600000", "601398", "000002", "600519"],
            "hk": ["00001", "00700", "00005", "03690", "09988"],
        }

        return APIResponse(
            success=True,
            data=symbols.get(market, []),
            message=f"成功获取 {market} 市场的股票列表",
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


async def _process_batch_async(client, queries, request):
    """异步处理批量查询"""
    # 这里可以实现后台处理逻辑
    # 例如：将结果存储到数据库或缓存，供后续查询
    pass
