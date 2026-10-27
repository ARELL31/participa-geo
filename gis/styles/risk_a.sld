<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
    xsi:schemaLocation="http://www.opengis.net/sld StyledLayerDescriptor.xsd"
    xmlns="http://www.opengis.net/sld"
    xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <NamedLayer>
    <Name>risk_a</Name>
    <UserStyle>
      <Title>Semáforo de riesgo A (línea base)</Title>
      <Abstract>Estilo de la línea base A. Mismos cortes y colores que el estilo B; sólo cambia la propiedad risk_a. No es un intervalo causal.</Abstract>
      <FeatureTypeStyle>
        <Rule>
          <Name>low</Name>
          <Title>Riesgo bajo</Title>
          <ogc:Filter>
            <ogc:PropertyIsEqualTo>
              <ogc:PropertyName>risk_a</ogc:PropertyName>
              <ogc:Literal>low</ogc:Literal>
            </ogc:PropertyIsEqualTo>
          </ogc:Filter>
          <PolygonSymbolizer>
            <Fill><CssParameter name="fill">#2E7D32</CssParameter><CssParameter name="fill-opacity">0.8</CssParameter></Fill>
            <Stroke><CssParameter name="stroke">#FFFFFF</CssParameter><CssParameter name="stroke-width">0.4</CssParameter></Stroke>
          </PolygonSymbolizer>
        </Rule>
        <Rule>
          <Name>medium</Name>
          <Title>Riesgo medio</Title>
          <ogc:Filter>
            <ogc:PropertyIsEqualTo>
              <ogc:PropertyName>risk_a</ogc:PropertyName>
              <ogc:Literal>medium</ogc:Literal>
            </ogc:PropertyIsEqualTo>
          </ogc:Filter>
          <PolygonSymbolizer>
            <Fill><CssParameter name="fill">#F9A825</CssParameter><CssParameter name="fill-opacity">0.8</CssParameter></Fill>
            <Stroke><CssParameter name="stroke">#FFFFFF</CssParameter><CssParameter name="stroke-width">0.4</CssParameter></Stroke>
          </PolygonSymbolizer>
        </Rule>
        <Rule>
          <Name>high</Name>
          <Title>Riesgo alto</Title>
          <ogc:Filter>
            <ogc:PropertyIsEqualTo>
              <ogc:PropertyName>risk_a</ogc:PropertyName>
              <ogc:Literal>high</ogc:Literal>
            </ogc:PropertyIsEqualTo>
          </ogc:Filter>
          <PolygonSymbolizer>
            <Fill><CssParameter name="fill">#C62828</CssParameter><CssParameter name="fill-opacity">0.8</CssParameter></Fill>
            <Stroke><CssParameter name="stroke">#FFFFFF</CssParameter><CssParameter name="stroke-width">0.4</CssParameter></Stroke>
          </PolygonSymbolizer>
        </Rule>
        <Rule>
          <Name>insufficient</Name>
          <Title>Información insuficiente</Title>
          <ogc:ElseFilter/>
          <PolygonSymbolizer>
            <Fill><CssParameter name="fill">#9E9E9E</CssParameter><CssParameter name="fill-opacity">0.7</CssParameter></Fill>
            <Stroke><CssParameter name="stroke">#FFFFFF</CssParameter><CssParameter name="stroke-width">0.4</CssParameter></Stroke>
          </PolygonSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
