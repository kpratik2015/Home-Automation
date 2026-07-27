<?php

declare(strict_types=1);

/**
 * Smart Home endpoints exposed to Alexa.
 * Friendly names drive voice: "turn on center fan", "turn on center light".
 */
function smarthome_devices(): array
{
    return [
        'center-fan' => [
            'friendlyName' => 'Center Fan',
            'description' => 'Center room chandelier fan',
            'displayCategory' => 'FAN',
            'commandOn' => 'fan-on',
            'commandOff' => 'fan-off',
        ],
        'center-light' => [
            'friendlyName' => 'Center Light',
            'description' => 'Center room chandelier light',
            'displayCategory' => 'LIGHT',
            'commandOn' => 'light-on',
            'commandOff' => 'light-off',
        ],
    ];
}

function smarthome_device(string $endpointId): ?array
{
    $devices = smarthome_devices();
    if (!isset($devices[$endpointId])) {
        return null;
    }
    return $devices[$endpointId];
}

function smarthome_power_capability(): array
{
    return [
        'type' => 'AlexaInterface',
        'interface' => 'Alexa.PowerController',
        'version' => '3',
        'properties' => [
            'supported' => [
                ['name' => 'powerState'],
            ],
            'proactivelyReported' => false,
            'retrievable' => true,
        ],
    ];
}

function smarthome_build_endpoint(string $endpointId, array $device): array
{
    return [
        'endpointId' => $endpointId,
        'manufacturerName' => 'Home Automation',
        'friendlyName' => $device['friendlyName'],
        'description' => $device['description'],
        'displayCategories' => [$device['displayCategory']],
        'capabilities' => [
            smarthome_power_capability(),
            [
                'type' => 'AlexaInterface',
                'interface' => 'Alexa',
                'version' => '3',
            ],
        ],
    ];
}
